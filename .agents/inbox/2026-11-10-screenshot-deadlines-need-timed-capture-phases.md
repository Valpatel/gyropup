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

## 2026-11-11 — distinguish an artifact budget from product readiness

The completed follow-ups and original failures are recorded in issue292. The
main `d694b3aa` run42938565751/job130254586945 again passed125 interaction
observations with no page errors, then exceeded the original15s capture limit.
Artifact13820361811 (ZIP SHA256
`4299d5f8550bf1276ffbace38c0b7c87184181d44892d25d2a00b97fae508a9f`)
records preparation31.47ms, fonts1.54ms and layout0.90ms. The native
`Page.captureScreenshot` request received no reply before the deadline. This
locates the pending operation; its internal cause remains unknown. A separate
pinned141 prospective30s control completed in11.888s, inside the old window, so
it did not reproduce or explain the slow attempts.

The test-only candidate gives that one required Chromium screenshot a finite30s
artifact budget, retaining15s as an explicit reference in its phase receipt. A returned
image after15s is labeled `completed-after-reference-bound`; the original
failures remain failed. Product readiness, interaction deadlines, pixels,
fullscreen prehistory and required screenshots stay unchanged. There is one
capture call, with no retry or fallback acceptance. This is an operational test
budget decision, not a performance fix or a claim about physical hardware.

Acceptance requires the full ordinary Chromium/WebKit campaign. At the end of
the Chromium campaign, an
isolated empty page deliberately stalls font readiness and requests one native
screenshot with a1s timeout. It must enter that wait, retain the identical
Playwright timeout through the observer, make one attempt, produce no PNG and
terminate within5s. This checks the actual deadline/error path without stalling
the product or changing its prehistory. The negative exercises preparation, not
an unresponsive native compositor; it cannot establish the cause of the delayed
`Page.captureScreenshot` reply. A future30s timeout is still a failure requiring
fresh evidence, not another automatic extension.

The negative holds one observed font network request and requires the underlying
font set to remain `loading`; its route is aborted in `finally` before closing
the owned context. Playwright1.56.1 awaits fonts in its utility JavaScript world.
A main-world property override of `document.fonts.ready` is therefore unsuitable:
it need not affect the wrapper in the other world. Independent source review
caught that distinction before the candidate was pushed or run in a browser.

### A demonstrated stall is engine-specific

Aggregate `06658a29` run42948429261/job130286927238 exercised the real control.
Artifact13824596197 (64 files, CRC verified; ZIP SHA256
`0038265d9b9fd121a33a98757e822126c7bce7c4340449a52d7fe7a970e78a66`)
retains the unsuccessful attempt. Chromium141 passed134 observations with no
page errors: the required Robot image completed in11.549s and the held-font
negative timed out in1001.71ms without producing its PNG. WebKit26 passed all133
product observations with no page errors; its Robot image completed in656.03ms.
However, its negative screenshot returned a PNG in82.65ms while the font set
reported `loading` before and after. The required rejection assertion correctly
failed. This is a control-fixture limitation, not evidence of a product defect
or a working WebKit timeout control. The internal WebKit reason is unproven.

Run the demonstrated native held-font timeout control only in Chromium, assert
that engine in the control itself, and disclose the unexercised WebKit timeout
path in the final report. WebKit keeps its full product suite and original15s
screenshot limit; the explicit fresh Chromium diagnostic also stays15s. Pure
observer error-propagation tests remain engine-independent. A future WebKit
native timeout control needs its own demonstrated stall; do not weaken the
rejection assertion or infer shared behavior from one browser's result.


## Root viewport coordinates and nested clips are different evidence

2026-11-11, #281 public A/V2/V3. [Selected immutable observations](../plans/printable-parts/public-observation/README.md) retain original report/cleanup hashes and actual PNGs. A's one queue image showed coupon tail/footer, although widths and horizontal header/cell deltas passed. Its harness scrolled only the window and never checked vertical visibility through the planner/table scrollers. A admitted only six JS/CSS assets: local compiled HTML and the deployed response differed by Cloudflare's exact beacon insertion, so HTML was never admitted. Await all seven explicit source/deployment checks before capture; bind the full response and exact byte difference, never strip arbitrary HTML.

V2 admitted seven identities but made zero screenshots. Its five-second Playwright scroll wrapper ended with an untimed waiting-for-stable log; that does not separate stable-state waiting from native scroll delegation. The collector also combined HTML's document-relative rect.top with root clientHeight, a viewport measurement. At scrollY 643 it invented clip bottom 257; at 1890, -990. Per [CSSOM View](https://drafts.csswg.org/cssom-view/#dom-element-clientheight) and [Overflow viewport propagation](https://drafts.csswg.org/css-overflow-3/#overflow-propagation), model the standards root viewport in viewport coordinates and retain its raw document box only as telemetry. Keep ordinary BODY/planner/table clips; do not blanket-skip HTML/BODY. Explicitly reject unsupported mode/zoom/propagation profiles. Retained V2 rows still fail real nested clipping after correcting only the root.

V3 used one native instant/center/nearest scroll and two time-separated passive samples, with the same connected header/document, unchanged horizontal offsets and hit proofs. It returned correct desktop queue/orders PNGs. This is prospective sampled geometry evidence, not consecutive-frame cadence, a renderer fix or an explanation of A's timeout. Pure controls use actual retained geometry plus clipped/occluded/shifted/unsupported negatives. No focus, font, scene or render workaround follows. V2's blocked Waveshare request remains retained; V3's empty failures do not erase it.

## A completed capture does not establish graceful shutdown

V3 queue capture took 8.293 seconds total, including 8.101 seconds native capture; orders took 15.894 / 15.792 seconds. Preparation, fonts and layout returned separately. The overall run still failed: graceful browser.close did not return within its unchanged 15-second bound. Context/work/response/positioning settlement completed, and the independent collector found the exact owned cgroup empty without errors. That proves terminal emptiness, not graceful-close success. Original screenshot and V2 wrapper timeouts remain unlocalized at their own unobserved boundaries; no further browser was run while authoring the canonical follow-up.

Record passive local-client counts/connection state, close events, and each cleanup phase's start/end/result at the original limits. Preserve the identical operation error, pending state and overall failed result even after a late return/disconnect. Do not retry/extend close, force rendering, or waive failure because the cgroup is empty. The repaired procedure's pure controls cover late completion, unknown snapshots, timeout and error identity. A new full public campaign remains separately bound/reviewed work, including phone, scope/status and twelve actual PDFs; two successful diagnostic PNGs cannot supply it.


## Panel selection must verify state instead of repeating a selected action

2026-11-11, full public B, immutable report SHA-256
38cda6166111781566ad119aee41ab0968cceb843d2f98e3fb003581813132be.
[The canonical B receipt](../plans/printable-parts/public-observation/attempt-B.json)
and [independent disposition](https://github.com/Valpatel/gyropup/pull/320#issuecomment-6807901966)
retain the failed result. All seven identities and actual Combined 224/30 passed;
queue/orders desktop PNGs returned once with V3-identical bytes. The helper then
clicked Buy unconditionally for made, although the resolved Buy tab was already
aria-pressed=true. Native click exceeded the original 15-second action limit
while waiting for visible/enabled/stable. Orders and made share Buy; queue is Print.
No made-target visibility or button-motion observation was recorded at failure.
This identifies a redundant action in source, not its stalled cause or proof a
zero-click path will complete the full campaign. No app/environment cause follows.

Build's actual panel function only toggles panel hidden and tab aria-pressed state.
A test helper whose contract is ensure-state may reuse an already selected panel
only when the actual connected target has positive CSS-rendered bounds, all tab/
panel identities and selected/hidden states agree, and a second read confirms it.
CSS-rendered does not mean in the viewport; existing root/nested clipping/hit and
alignment checks remain mandatory. Missing/hidden/disconnected/disabled/empty/
inconsistent targets fail, never receive a failed-action waiver. A genuinely
unselected Print/Buy request still uses one real native click and original target
visibility wait with post-state proof. Neither programmatic setters nor forced
input replace those transitions. Keep original errors and bounded passive before/
after action receipts; a failed diagnostic cannot replace the native failure.

Pure controls reject B's pressed flag without the missing target evidence and
cover both real transition directions, zero-click valid reuse, failing states,
failed native actions/collection, document changes and ineffective transitions.
The complete source/paper/lifetime requirements are unchanged. B cleanup returned
in 595 ms / 12,726 ms for context/browser with terminal owned cgroup empty and no
collector errors; overall B is still failed, and V3's failed close remains failed.
No made/mobile/scope/status/reload/PDF acceptance, new browser or replay is claimed
while authoring this repair.
