# An unoccluded model can still be too small to use

2026-11-10, independent visual review of PR #286 at runtime source `ca7f2226`.

## Actual evidence

```text
2026-11-10: npm run test:instruction-docking
PASS chromium 103 actual docking/control states
PASS webkit 103 actual docking/control states
native 844×390: mobile=true, pointerCoarse=true, all touch targets hit,
vertices>0, unoccluded=true
```

The actual screenshot nevertheless showed a tiny model between the navigation
and the open bottom sheet. Navigation ended at y132; the sheet's tabs started at
y225. The camera's 12px overlay gaps reduced that already small strip further.
The full passing receipts and actual image remain in commit `95d85ef9`; the image
is `plans/instruction-docking/after-844-phone-native.png` there.

## Why the green check was insufficient

The guard checked whether projected real mesh vertices lay inside the canvas and
outside every overlay. Camera fitting could satisfy that by shrinking the model
into almost any remaining strip. Pointer targets and fitting bounds established
reachability and non-overlap, not a useful viewing area.

## Corrective rule

For short coarse-pointer landscape at 600–1000px wide and <=500px high, use one
right-hand tabbed pane and reserve its actual width in the camera's right inset.
Keep portrait's bottom sheet and fine-pointer desktop's independent panels. The
selected-part popup shares that side pane below its permanently visible tabs.

The regression now requires a 300px model lane, 210px available model height and
at least 150×120px of actual projected geometry for its known real turret step,
in addition to the existing real hit tests and unoccluded-vertex check. Both
normal and expanded pane widths must update the inset. Record the actual pane,
insets, pointer mode and projected model box; inspect the resulting image too.

## Limits

These thresholds cover the named fixture, viewport and presentation promise;
flat parts or another authored camera need their own meaningful projected bounds.
They do not qualify geometry, fit, fabrication or hardware operation.
