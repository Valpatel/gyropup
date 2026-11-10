# Selected-part details must occupy space already reserved by the viewer

2026-11-10, PR #286, original failed CI run 42863757535 / job 129997763341.

## Actual command and failure

```text
2026-11-10: npm run test:build-guide
PASS nineteen pure tests; PASS current poster binding
PHASE forward-1 ... PHASE forward-12
AssertionError: {"x":509.48332798306785,"y":620.3323655178513,
"name":"pan_servo","unoccluded":false}
false !== true
```

The CI image shows the floating Selected part popup at x284–584 over the isolated
servo, intercepting the intended real canvas point. The core sequence selected
`pan_servo` from the hierarchy, used the standard Isolate action, then tested its
first triangle's projected centroid. All original twelve frame checks had passed;
this was a real overlay failure, not a timeout or missing model. Native Chrome
reproduced the same point locally before the fix. Original CI failure JSON, image,
exact assertion/phase excerpt, source links and raw digests are retained under
`plans/instruction-docking/ci-e87-popup/`.

## Why the previous checks missed the regression

The desktop layout moved 1280px from the shared mobile sheet to independent docks,
but its selected-part popup still floated next to the clicked hierarchy row. The
camera reserved Parts/Tools/instructions, not this extra central overlay. The
broader state checks did not execute Isolate with that popup open.

## Corrective rule

Desktop selected-part details share the existing Parts dock. Direct canvas
selection opens that dock, so the camera reserves it before the details paint.
Keep all detail fields, appearance/isolate controls and manufacturing actions.
Portrait and short-landscape compact panes keep their established placement.

Preserve the original centroid and native mouse click in the regression; do not
move the test point around the popup. Also assert the popup stays within Parts
and that Parts, Tools and instruction controls remain real reachable targets.
Exercise the same isolated selection/canvas click in windowed, native fullscreen
and expanded fallback layouts, at both desktop widths, alongside actual touch
pane placement checks.

## Limits

The original failure remains failed. Local passing coverage is distinct from the
normal pinned CI run. These are UI and software interaction checks, not hardware
or manufacturing qualification.
