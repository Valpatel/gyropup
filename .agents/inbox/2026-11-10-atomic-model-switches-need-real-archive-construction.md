# A mode-switch fixture cannot replace the real archived constructor

On2026-11-10, issue193's additive current/recorded presentation controller
passed synthetic held/failed/stale/repeated-switch and disposal controls. The
first test through the real v2 entry and tracked archived rig failed:

```text
node --test tests/site/models/test-current-robot-data.mjs
7 PASS / 1 FAIL: TypeError: turret.setExplode is not a function
buildRigRobotV2 -> setPresentation -> setExplode
```

Cause: recorded-only construction now reuses existing turret effects without
loading a newer bench assembly. Its effect API lacked the existing no-current-
submechanism explosion operation. A lightweight holder double did not exercise
that constructor boundary. The recorded-only adapter now explicitly leaves
archived turret submechanisms unchanged; source-body explosion/reset remains
the original owner. No archived mesh/manifest, qpos or physics value was edited.

```text
node --test tests/site/models/test-current-robot-data.mjs
8 PASS,447.8ms: synthetic current geometry + real tracked archive entry;
whole-holder metadata/source/muzzle/mass/qpos roundtrip; no unrelated bench or
current-attachment downloads; held/stale/cancel/resource controls remain passing
```

Rule: exercise the real public constructor and retained input files alongside
small lifecycle doubles. Commit body, sensors, limits and source/readout basis
atomically; a valid current mesh tree must not acquire recorded qpos or mass.
Preserve original errors and inspect actual downloaded/constructed ownership.
These Node/Three controls do not replace actual266 browser vertex captures,
independent motion traces, artifact acceptance or physical qualification.

## A stable effect parent must preserve the old public visibility operation

Independent review [4530151719](https://github.com/Valpatel/gyropup/pull/287#discussion_r4530151719)
reproduced a second boundary: Play hides `robot.turret.laser.visible` while
entering the bench or replacing a model. The new stable attachment was a parent,
but proxied `updateLaser` restored only its active child. Both individual flags
were valid booleans while their combination kept the beam invisible on return.
The old single-laser operation restored visibility.

```text
2026-11-10 regression before correction:8 PASS / 1 FAIL, current cached return
independent counterexample:parent=false, active child=true, effective=false
node --test test-current-robot-data.mjs test-turret-stops.mjs after correction:
12 PASS,445.5ms
```

The product wrapper now mirrors the active effect's resulting visibility onto
its stable stage attachment, hides inactive cached effects, and clears the
attachment when committing a different complete mode. A regression uses the
actual `buildTurret` effect API through current/recorded/current repeated modes,
the exact page-owned hide/return calls, explicit disable and turret detachment.
Rule: when wrapping an existing public object, preserve operations that restore
its state as well as reads/writes to that object. Inspect ancestor visibility,
not just the active child's flag. The accepted226-file conversion is unchanged;
this source correction does not authorize a conversion rerun or browser capture.
