# Untimed font completion does not localize a screenshot deadline

2026-11-10, issue292 / diagnostic PR294. Main67d5ea2f run42889052519,
job130084998921, and PR289cdcf7a4c run42896715114, job130111635244,
both failed at the same stopped Robot `page.screenshot({timeout:15000})` after125
passed observations and no page errors. Their failure reports have the same five
source hashes and are byte-identical (originalSHA317f7bdc995a0488f7f9fd80929ebd943ef147cc70ccb4272a64ec54b9e3c94a).
Both later playing sequences were unrun. The catch-path PNG is a diagnostic,
not the missing required screenshot. Original reports, artifact identities,
actual images and dated log excerpts are retained in
`plans/docking-capture-diagnostics/`.

```text
page.screenshot: Timeout15000ms exceeded
  taking page screenshot
  waiting for fonts to load...
  fonts loaded
125 observations; errors[]; stopped native Flip/Rotate/Loop passed
```

Pinned Playwright1.56.1 screenshot preparation/fonts precede Chromium's
Page.getLayoutMetrics and Page.captureScreenshot, then cleanup. Client PNG file
writing occurs after the channel result. Progress entries have no per-entry
times; “fonts loaded” says the wait returned, not how much of the shared15s
budget it consumed. The exact stalled phase and its cause remain unknown.

A separately authorized one-context Chrome151 observation passed in13.096s
whole-operator /1.953s screenshot, with9.143ms preparation,0.835ms font wait,
0.304ms layout metrics,1937.455ms capture and2.877ms cleanup. Both fonts were
loaded, requests empty, frames advanced, and no GL loss/error occurred. It
validates observation wiring only: it differs from CI141 and omits the preceding
125-state/native-fullscreen/context history. Observer reads/wrappers add timing
overhead. It cannot clear either historical failure or prove contention.

## Corrective diagnostic rule

Observe the original capture boundary in the real campaign, forwarding original
protocol calls/results unchanged and retaining metadata only. Record bounded
before/after document identity, font, visibility, renderer frame/work, canvas
context-loss and request state. Preserve the original15s screenshot rejection,
original error and incomplete outcome regardless of telemetry/write failures.
Pure controls must reject a controlled failed capture, make exactly one capture
attempt and leave later phases unrun. An existing catch screenshot is never a
substitute. No font bypass, focus/stage change, retry or timeout increase follows
from this evidence.

## Hypotheses and limits

The playback context follows a phone context closed while native fullscreen may
still be owned. Source awaits context.close but old receipts do not record its
native fullscreen/compositor transition. Observe ownership/visibility before
close, completed close and the new context; do not force an exit or foreground.

The heavy171-part scene and first section/capture cycle may matter, but the
source already gives materials their clipping plane at creation and enables
local clipping before rendering. updateSection mutates the existing plane's
normal/constant; it does not create geometry/materials. That does not establish
whether native draw/shadow/shader/compositor work dominates. Frame/call/triangle,
program and context metadata are observations, not a hardware performance claim.

No product correction is claimed. The next pinnedCI campaign must provide the
missing phase observations before choosing a mitigation. No local full browser
campaign or native run was started for PR294.

## Actual573 pinnedCI located the pending protocol operation

Run42899887112/job130122907263 failed with the original15s error and125 passed
observations. The newly recorded preparation12.574ms/fonts1.313ms/layout0.393ms
all completed, then Page.captureScreenshot remained unanswered through the
remaining~14985ms. Cleanup5.431ms returned; the screenshot API rejected after
15006.676ms. The observer had no errors/dropped calls. Full immutable identities,
original failed report and actual diagnostic PNG are retained in
`plans/docking-capture-diagnostics/observed-573/`.

Before/after native snapshots remained available and showed the same visible,
focused, complete, nonfullscreen document, loaded fonts, no requests/context loss
or stage error, frame37→48 and programs5. Endpoint frame advancement is not
per-frame cadence, nor does stable program count rule out all native driver costs.
The phone was native-fullscreen before its awaited context close; zero contexts
followed close, then a new playback context. This confirms lifecycle sequence,
not causality. The internal browser capture reason remains unknown.

The next proposed contrast reuses the original stopped Robot capture in a fresh
**pinned141** browser with no prior context or scene. Separate scoped evidence and
an additive matrix case preserve the normal full campaign and all failures. No
control is run until source/action review; a different localChrome151 success is
not that contrast. See `plans/docking-capture-fresh-control.md` for the bounded
command, runtime guards and interpretation limits.
