# Layout readiness must wait for rendered fonts without waiting for every resource

On 2026-11-05, PR #222 layout CI reported zero layout findings but two README
navigation timeouts, leaving four views unmeasured. The job correctly failed.
The particular stalled CI request was not identified. A controlled real navigation
with a held 64 × 20 image reproduced the global-load failure class.

Dated browser evidence:

```text
actual load helper: page.goto(load) timed out while document text was present
real navigation: readyState=interactive, fonts.status=loaded, fonts.ready still pending
```

Changing navigation to DOMContentLoaded alone was insufficient: both our loader
and pinned Playwright 1.56.1's screenshotter awaited document.fonts.ready, which
remained coupled to page completion even with no font download pending.

Fleet job 164 then caught a real flaw in the first draft: reading opaque CSSOM
rules raised SecurityError on two tablet research pages, leaving four views
unmeasured. Opaque rules are not evidence of a failed stylesheet load.

Corrective rule: observe native stylesheet load/error events before parsing to
await linked/importing styles, rather than reading cross-origin rules. Then explicitly
load actual rendered text fonts/characters under a 30-second bound, then retain
the existing settling and media checks. This one harness sets Playwright's pinned
PW_TEST_SCREENSHOT_NO_FONTS_READY flag to avoid only the duplicate global wait.
No browser FontFace state is forged. Real stylesheet load errors or font errors
remain failures; a loaded opaque sheet is accepted using its native event.

Controls use the actual load/audit helpers: a held small image remains pending
while measurement completes; a held large on-screen image is rejected as never
loaded; an actual opaque cross-origin Inter import/font is held, then decoded before
measurement; a failed stylesheet is rejected before measurement.
Dated verification commands:

```sh
node tools/test-empty-space.mjs --controls
node tools/test-empty-space.mjs --pages=/site/pages/research-lfp-batteries-md.html,/site/pages/research-leg-suspension-md.html --sizes=tablet-768 --schemes=light,dark
```

The affected tablet pages measured all four views with zero findings. Existing
planted blank image/canvas, missing image, gap and squeezed-column checks
still reject in both themes. Pixel/media thresholds and two-frame settling are
unchanged. The held-resource control fails if an SDK upgrade removes the flag.

Limits: the control demonstrates the failure class, not the identity of the old
CI request. Core model/report readiness remains required. No readiness timeout is a
successful validation. This is a product-specific layout harness, not a new
network availability or universal font-rendering guarantee.


## Text-wall readiness has the same global-load failure class

On 2026-11-05, PR #224 at `bd95fb6d` failed in tools/test-walls.mjs:71,
waiting for global load on /site/pages/readme-md.html. Job 127645161957
(run 42142254463) had 21-second dependency setup and took 7m57s overall;
its exit1 was a 30-second readiness timeout, not global cancellation or a wall
threshold result. The particular pending CI request was not identified.

A controlled run extracted the actual walls navigation statement and held the
real README Stars request. It timed out at the control's 2-second bound while
the document was interactive, fonts.status loaded and the title present; the
pending badge had a 0×0 box and no declared height. This proves the failure class,
not that Stars caused the observed CI failure. All owned resources were closed.

Shared native stylesheet/actual-text font readiness is extracted without changing
its behavior. Walls must additionally decode all unfolded relevant/unknown-size
images across the entire article, activating actual native lazy loading even
offscreen. A currently zero-size image is not assumed decorative. Return to the
top and settle two frames before the unchanged wall measure; fail missing/held
primary media before measurement. Existing wall geometry, thresholds, backlog
ratchet and planted cases are unchanged.

The seven README status badges now reserve both dimensions, using measured SVG
widths 158/236/78/112/116/71/90 and height20. Fixed inline sizing overrides the
portal's height:auto rule; contain sizing preserves artwork as status contents
change. All seven links/alt semantics and GitHub width/height attributes remain.
The badge source URL is not a readiness exemption: the explicit fixed small box
must actually match its laid-out dimensions. README and doc-page styling were
checked against the actual capture-input list; neither is bound to highlights.

The actual README control holds its real Stars request, calls the real walls
loader/measure while it remains pending, then decodes a deliberately wider SVG
response and requires identical article/wall geometry. Other controls hold a
real font, hold an offscreen unknown-size lazy primary, fail a missing primary,
and fail a stylesheet. Each uses bounded barriers/finally cleanup. Source and
fresh-build positive controls remain pending in this initial implementation;
no successful validation is claimed yet.

Fleet 186 at `ed8000ab` failed before any sweep: the planted lazy-primary case
found that readiness had completed while its request was still held. The real
README geometry and awaited-body-font cases had passed before it. This was an
actual source defect caught by the control, not provisioning or cancellation.
Pinned Playwright 1.56.1 truth-tests a predicate's returned Promise before its
false value resolves; an actual `waitForFunction(async () => false)` probe
returned false in 19 ms despite a 2-second deadline.

Image readiness now polls synchronously for completion and valid natural size,
then launches native decoding into a captured per-call completion/error state
and polls that state synchronously under a 30-second bound. Actual text-font
loads use the same bounded-state pattern; final fonts.status=loaded is enforced
instead of returning an unchecked asynchronous false. No native font or image
state is forged.

The font control now holds a real rendered pseudo-element font: ordinary text
loads can finish while that face remains loading. It must time out before any
measurement, then pass a fresh actual-loader run after release. A loaded primary
whose decode never resolves must also time out before measurement. Together
with the real README, offscreen lazy/missing primary and CSS-error cases, all six
controls passed locally with the corrected harness against fleet 186's product
artifact; this is scoped local evidence, not a fresh corrected-source fleet pass.
All ordinary bounds and geometry/backlog thresholds remain unchanged. The failed
186 attempt stays failed, and the particular original CI request remains unknown.

Fleet 187 at `998fd92c` then failed the actual README held-badge positive at
the font boundary, before any sweep. An observer-only same-source/bounds run,
fleet 188, preserved these native states at 2022 ms:

```text
used font-load promises: done=true, error=null
auto-loaded Inter and JetBrains Mono: status=loaded, loaded promise fulfilled
FontFaceSet.status=loading; document=interactive
only pending request: actual held Stars badge
result: 30-second timeout; owned browser/listener closed
```

This establishes the global-set/document-environment coupling for this observed
case, rather than inferring it from a timeout. The [CSS Font Loading draft's
environment rule](https://drafts.csswg.org/css-font-loading/#fontfaceset-pending-on-the-environment)
also explains why set-level metadata can await document completion after the
individual faces are available. Local installed Chrome and bundled Chromium
both passed the earlier control, so this is not labelled a universal engine or
architecture failure.

The font contract now keeps the actual text-load promises and their returned
native faces, requires returned faces loaded, rejects native face errors, and
waits while any native face is loading (including the rendered pseudo-element
face). Unused unloaded faces are not forced to load. Set-level status is recorded
only as diagnostic metadata; no native state is overwritten. The held pseudo-font
and real text-font controls remain, with an additional actual pseudo-font 404
negative. These guards prevent removing global metadata from becoming a blanket
font bypass. Fresh corrected-source controls and sweeps remain required.

GitHub run 42148700612 attempt 1, presentation job 127666350122, also
failed at the old `998fd92c` font boundary. Its six readiness controls passed
before the ordinary full-page loop timed out; that failure did not identify the
route. This is additional evidence against an ARM-only diagnosis, not proof
that the unobserved page had the same pending request as fleet 188. The actual
wall loader now adds route context while retaining the original error as its
cause, with the same readiness rules and bounds.

### 2026-11-10: A real stopped-stage negative must reject a Promise-false observer

The first hop-budget draft repeated this failure class by using an async
waitForFunction predicate that called an exposed Node guard. Actualstage.stop
left jump.t0.5/y0.143 and11frames while the observer falsely accepted; the next
unchanged gamepad settings assertion independently rejected jump.t0.65 instead
of null. All apparent newPass values from that draft remain
[rejected evidence](../plans/assembly-staging/ci-frame-budget/rejected-observers/README.md).

The corrected polling adapter is passed directly to Playwright as a synchronous
function, invokes the exact pure guard/read-sample functions through same-document
handles and explicitly rejects non-boolean guard results. Unit tests call that
actual adapter for both false and true results and reject a Promise-valued guard.
The real stopped-stage control now rejects after10.022s with no frame; the actual
1000ms-gated hop genuinely completes within the separately documented stage-dt
and wall budgets. A private control first created handles before navigation and
was correctly refused after navigation; preserve that unqualified setup failure.
No product trajectory, browser error or failed evidence is bypassed.
