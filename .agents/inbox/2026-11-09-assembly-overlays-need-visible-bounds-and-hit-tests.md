# Fit visible geometry and test actual overlay hit targets

2026-11-09 local / 2026-11-10 UTC, issue #266 and PR #267.

## Evidence

- Initial Build workspace at `b46a0c7a` reused the real playground robot inside
  the existing guide stage. `Box3.setFromObject(robot.group)` also included hidden
  FOV geometry, producing a tiny robot in the actual browser capture. Traversing
  visible meshes and unioning their actual transformed bounds restored useful
  framing without changing model vertices, units, joints or mounting transforms.
- The independent `6a7b6b2f` browser study completed all 36 step rectangle checks
  at desktop and phone widths, but visual inspection still found global app
  navigation over the workspace controls. Stable rectangles do not prove usable
  controls. The original bounded study timed out; partial successful checks are
  retained separately from its failed overall result.
- Actual Chromium at `fb846019`, using
  `WORKSPACE_WIDTH=390 node tests/site/assembly/test-build-workspace.mjs`, failed:
  `Expand: width 77.640625, height 36, reachable true` against the existing 44px
  touch target requirement. The control was corrected; the threshold stayed 44.
- At `8286ee61`, the same real 390x844 probe passed initial hit targets, distinct
  Robot/Combined context/mount checks and all twelve stable unoccluded turret
  states, then failed at the native Appearance label lookup. The actual screenshot
  showed the inspector and select; an explicit accessible name was added.

- At `3e839ab6`, the exact legacy route `snapshot=turret-wip-4866459e2abd&assembly=robot`
  became blank. Fresh-browser evidence showed `Cannot set properties of null
  (setting 'hidden')`, followed by `Viewer is disposed`. The hierarchy rewrite
  removed an instruction/BOM wrapper while `workspace.present` still required it.
  The loader disposed the newly published viewer after the presentation error.
  `80453a22` removed the obsolete reference and postponed prior-viewer disposal
  until successful presentation, restoring the prior scene on failure.
  Exact-route, native assembly switch, held-context/manual-step and completed
  asynchronous-disposal controls passed Chromium and WebKit. Canonical hashes
  and actual rendered observations are in
  `../plans/versioned-build-guide-route-proof.json`.

## Cause and corrective rule

Three-dimensional bounds can contain intentionally hidden context. Fit only the
visible modeled geometry. Keep the expected CAD frame independent from camera
fitting, and never correct a framing problem by altering model placement.

Overlay acceptance needs both geometry projection and real browser hit testing
at the actual viewport dimensions. Check `elementFromPoint`, touch target size,
global fixed navigation, nested scrolling and initial anchor settlement. A
full-page capture at a narrow width with a desktop height is diagnostic only;
record the exact viewport and take viewport captures for phone acceptance.

A renderer may be loaded successfully while product presentation still fails.
Do not dispose the prior coherent scene until the replacement has painted its UI.
When overlay DOM is restructured, run the exact default and legacy assembly links
in fresh contexts; waiting only for an unrelated procurement-ready flag misses a
blank guide. Async disposal evidence must wait for the old operation to finish,
not an arbitrary sleep.

Use separate bounded browser scopes and retain failed receipts. A timer cap,
a later failing control, or a screenshot closure cannot turn earlier partial
observations into an overall pass.

## Limits

These checks establish presentation and interaction behavior. They do not prove
physical fit, strength, insertion paths or robot qualification. Playground
context retains its own interim body and mirrored leg representation; it is
separate from source-bound CAD assembly guides.
