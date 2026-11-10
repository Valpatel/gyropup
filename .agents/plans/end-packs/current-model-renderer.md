# Current and recorded renderer source, before conversion/capture

2026-11-10. The independent e6 data-contract review is
[5848651024](https://github.com/Valpatel/gyropup/pull/287#pullrequestreview-5848651024).
Its converter, source tests and source-plan files remain byte-identical. No
artifact conversion CLI, CAD/native construction, browser, projection, poster,
public guide copy or artifact acceptance runs in this source checkpoint.

The additive `current_robot.js` builder uses the existing shared `readAsset`
hash/deadline/asset-root contract and existing STL/geometry validation. A caller
must supply an externally reviewed manifest hash; a manifest cannot accept
itself. Four concurrent transfers own an abort scope. Partial, failed, cancelled
or late results never produce readiness. Every original triangle remains in
exactly one loaded source part/partition. Product owner groups localize actual
world geometry through their inverse home world matrices; original units/basis
and proper right-module rotation are retained.

The existing five-bar solver moved unchanged to `robot_kinematics.js`; existing
sensor effects moved to `robot_sensors.js`, accepting the fully selected mode's
own mount datums. No new kinematics engine or generic viewer was added. The
existing turret effect/control builder can use supplied source-owned frames
without its procedural stand-ins. Removed stand-ins and owned model/effect
resources are disposed; shared foam-ball resources and caller eye textures are
excluded. Current demo launch speed uses the existing play configuration, not
a newly claimed ballistic simulation.

`robot_presentations.js` extends the existing product current/recorded switch
to complete holders. It caches at most current/recorded, commits body, legs,
turret, sensors, bounds/limits, effect APIs and readout basis together, and keeps
recorded loading off-scene until a current request commits it. A newer choice
cannot be replaced by a late request. Failure preserves the original error and
usable current graph. Disposal cancels owned loading and disposes late holders.
Recorded-only construction reuses the actual old v2 rig files and qpos path;
it downloads neither a newer bench turret nor current link attachments.

The public entry's `CURRENT_ROBOT_SOURCE` is deliberately still null in this
pre-adoption source checkpoint, preserving the existing default route. An
explicit current binding selects the new full holder and never catches a failed
current load as a reason to display an archive. Separately reviewed artifact
adoption must populate this authority atomically with the actual current assets.
Until then no public render or new current artifact is claimed accepted.

Current identity/mass readouts use the committed holder. Current mass/COM and
physics remain pending rather than becoming0kg or a retained study's result.
Unsplit D69 hub/axle and turret motor internal rotation remain unresolved; the
separate tyres and flywheels still animate and require actual spin traces.
Landing/talk home pose and poster hook use the model's exact300mm normalization,
while the retained route keeps its previous0.6 setting. Firmware, leg limits and
historical rig geometry/recordings remain unchanged.

Checks run without a browser/native kernel:

```text
node --test tests/site/models/test-current-robot-data.mjs tests/site/controls/test-turret-stops.mjs
11 PASS,445ms: actual current builder on explicit synthetic triangles; real v2
entry + complete tracked archived rig; source/metadata/procurement separation;
real live solver, wheel signs, firing/explode; corrupt/missing/hash/partition
controls; held failed/stale/disposed loads; every owned visible/effect resource
disposed exactly once; original archive qpos/muzzle/mass/mesh transforms retained.
```

These are source/lifecycle checks, not actual current-mesh motion evidence.
Before capture: freeze an independent finite source-FK corpus and tolerance,
shared hinge/closed-loop required-pose contracts, and the complementary complete
mesh/translate-only-envelope checks. Verify actual renderer world vertices and
anchors, non-home both-side cases, wrong-pivot-at-correct-home, rotation/mirror,
unit/sign/parent/ownership/missing negatives, firing/reset and repeated complete
mode transitions. Independent source/action and artifact review remain required.

The next data action should be the existing pure converter CLI into a fresh
external output:226 files (224 original STLs + original collection + manifest),
fixed source/input/runtime identities, a short timeout and preservation checks.
No native service/compute pipeline is needed for this seconds-long conversion.
Public artifact/guide/CI adoption, README projection, fallback poster and both-
engine current published-consumer checks remain separate reviewed steps. Original
issue193 mechanical retention/fit/clearance/support/load/drop requirements stay
open after consumer publication.
