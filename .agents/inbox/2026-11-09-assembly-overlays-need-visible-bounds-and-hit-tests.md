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

## State attributes must not become action hooks

At `ce31b3b3`, the first startup probe found that the workspace's `data-sheet-size`
state attribute also matched a generic action selector. Assigning the resize
control's text replaced the workspace subtree; a ready flag or zero page errors
could not establish usable 3D. `5866182e` split state into `data-sheet-size` and
user action into `data-sheet-resize`; `330fc021` required typed button selectors.
The same exact-route probes in both engines then verified an attached canvas,
nonzero visible meshes, real instructions and the navigation dropdown.

Keep state markers and action hooks distinct. Resolve actions as typed controls
(for example `button[data-sheet-resize]`), and fail explicitly when required DOM
is absent. A startup smoke must inspect the actual attached renderer and visible
geometry as well as meaningful instructions/navigation; procurement readiness is
not sufficient.

## Recover initialization before the first successful model

2026-11-10, PR267 current-head CI supplied three concrete controls:

- Run42793469404 layout job129752517272 rejected the actual hierarchical guide
  because its old readiness control still required exactly three flat chapter
  buttons. The corrected barrier checks an attached live canvas, visible meshes,
  unique real part rows, and the bound guide's step dropdown/text. The held-model
  negative remains: procurement readiness cannot release assembly readiness.
- The same run's Print job129752517254 timed out on a second same-page navigation
  before injecting its project failure. The product cause was not established.
  Independent Print boundaries now use fresh contexts and DOMContentLoaded plus
  actual guide readiness, with unchanged limits/assertions. Service workers are
  blocked only for controlled HTTP faults, and request counts prove the rejected
  project and restored retry actually crossed that boundary.
- Run42794535081 Build-portal job129756320087 passed core and version-switching,
  then timed out after a rejected initial snapshot: selecting a valid snapshot
  changed the select but did not load a model. An actual Chrome counterexample
  on `c7175631` also clicked Robot and observed `active:false, canvases:0`, with the
  original unavailable-snapshot status. Snapshot selection treated no active
  model as an inactive assembly; workspace choice returned before the loader.
  The rejected initial route also skipped history/pagehide registration.

Do not infer that a recovery handler can require successful initialization.
Explicit valid choices must enter the loader when no model exists. Install
history and disposal handlers independently of initial route success, replacing
old routing handlers on retry. Test the original rejection, every enabled
assembly choice, subsequent back/forward, and disposal. Keep a previous coherent
model when a later invalid route is rejected; do not silently substitute another
snapshot. These are presentation/lifecycle rules, not physical qualification.

The first actual recovery probe at `81740925` found a second initial-state
boundary: on390px, the navigation row intercepted Robot because toolbar/nav
measurements returned before any viewer existed. Measure floating controls before
the viewer guard; loading and rejected routes must retain reachable choices.
The same recovery regression includes a real back/forward round trip and pagehide.

Current-head Print job129756319817 passed both original and prepared-project
HTTP404 recovery, then its redundant pre-fullscreen diagnostic screenshot hit
15s after fonts had loaded. The catch screenshot succeeded and showed a clear
complete model; no fullscreen/Print assertion had run yet. The duplicate capture
was removed, retaining sealed visibility/focus/button bounds and every actual
fullscreen/Print assertion. Do not relabel that successful prefix as fullscreen
acceptance, or increase the timeout to hide the capture failure.

## Static exports must reveal intentional task panels

2026-11-10, run42794535081 presentation job129756319770 reached a real Markdown
failure in subtest4: the Supplier part number table was absent. Buy and Setup
were intentionally hidden browser panels, and the serializer's generic `[hidden]`
cleanup removed them. The static adapter now exposes only the direct workstream
wrappers before cleanup; unavailable hidden descendants remain excluded and the
browser DOM stays compact. The actual renderPortal→Markdown control preserves
all279 order rows, seven columns and four workstreams, including rows beyond
pagination; a hidden-child negative stays omitted. All six existing Markdown
tests and eleven privacy tests passed. Reveal intentional presentation containers
for static export, rather than stripping every hidden attribute or weakening the
original table/download assertions.

## An explicit version must resolve its indexed assembly

2026-11-10 actual fresh WebKit at `bea6b2b6` requested the Robot540 and Turret486
snapshot-only URLs. Both instead loaded Combined540 with233 model parts. The
initial desired-assembly default ignored the explicit snapshot's indexed owner.
Resolve a nonempty explicit snapshot to its index row's assembly when no assembly
is supplied; retain explicit assembly overrides and keep the bare page's Combined
default. Centralize this in location parsing so initial load, history and canonical
version links agree. Tests cover all three real version-only routes, the bare
default, explicit mixed override, unknown rejection and Combined canonical reload.
Do not infer assembly from a label/revision string or silently substitute another
version. The failing observation remains distinct from later fixed-head acceptance.

Current-head50cc Print job129780849681 then reached the real fullscreen click,
but immediately read `data-fullscreen:null` before the asynchronous transition
completed. Both HTTP404 boundaries passed and errors were empty. The catch image
already occupied the viewport, but that alone could not identify native versus
expanded fullscreen. Await actual document.fullscreenElement, matching mode and
pressed-control state (or the intentional expanded-denial state) before testing
Print escape. The same30s bound remains; no fixed sleep or timeout increase is a
substitute for the native completion predicate.
