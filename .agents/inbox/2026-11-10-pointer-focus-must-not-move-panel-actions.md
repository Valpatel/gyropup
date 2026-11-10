# Pointer focus must not move a panel action before its click completes

2026-11-10, PR #286, original failed CI job 129997763644 / run 42863757535.

## Actual command and event evidence

```text
2026-11-10: PLAYWRIGHT_BROWSER=webkit WORKSPACE_CASE=interactions npm run test:build-workspace
Expected section {axis:x, flipped:false, depth:1}
Actual section   {axis:z, flipped:true, depth:0.4}
```

Chromium had passed in that same job. An instrumented native WebKit core sequence
also reached the Reset button but left mode=wireframe, explode=1 and section=.01.
Its actual event trace identified the failing boundary:

```text
pointerdown: Reset target=true, button.y828, tools.scrollTop209, pointer.y850
mousedown:  Reset target=true, button.y871, tools.scrollTop166, pointer.y850
focusin:    Reset focused,     button.y871, tools.scrollTop166
pointerup:  INPUT target,      button.y871, tools.scrollTop166, pointer.y850
click:      DIV target,        button.y871, tools.scrollTop166, pointer.y850
```

Original CI failure JSON/image/log excerpt and raw hashes, plus the instrumented
local trace, are retained in `plans/instruction-docking/ci-e87-interactions/`.
The original failure remains failed; this was not an assertion timeout.

## Why actionability was insufficient

The pointer initially hit the enabled Reset button. WebKit scrolling then
moved the scrolling panel during the native pointer sequence, so mouseup landed
on the range input and the resulting click never activated Reset. A button's
focus or successful pointerdown is not evidence that its click handler ran.

## Corrective rule

Keep Reset in a fixed Tools footer, and Isolate/Print in a fixed Selected part
footer. Only their variable controls and detail content scroll. Keep native
focus, click and keyboard semantics unchanged. Explicit focus/scroll restoration
and pointer-focus interception candidates were rejected because the unchanged
regression still caught the target moving; those guards are not shipped.

Both existing Reset regressions retain their original model/section state
assertions and additionally require trusted native pointerdown, pointerup and
click to target Reset at a stable rectangle. Touch and Tab/Enter checks cover
Reset, Isolate and the multi-action footer. Keep exact event coordinates and
scroll positions when a future native control boundary fails.

## Limits

This correction is scoped to the workspace's scrolling action panels. It does
not infer a general browser focus defect or justify applying focus interception
to unrelated controls.
