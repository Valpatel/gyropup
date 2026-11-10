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
