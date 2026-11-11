# Late overlay styles must refresh camera insets before claiming startup framing works

On 2026-10-29 UTC, a fresh manual playground opened with its head and body clipped above the toolbar, although tests that switched models on an existing page passed.

Evidence at 03:15 UTC: a Chrome/SwiftShader browser at 1280×900 opened `/designer/sim.html?run=none&demo=0&sound=0` in a fresh context. A Playwright route held `character/talk.css` until `document.body.dataset.ready === '1'`, then released it. Before CSS, the talk body occupied `{top:68,width:1280,height:101.58}`; after CSS it occupied `{top:623,width:420,height:124}`. The camera retained `offsetY:396` in its 836px canvas after both measurements. The corresponding fresh screenshot showed only the legs below the toolbar. The reproduction command was `node /tmp/gyropup-fresh-layout-probe.mjs`; its deterministic route-hold sequence is now retained in `tools/test-robot-controls.mjs`.

Cause: `mountTalk` injects its stylesheet asynchronously. The simulator measured the unstyled normal-flow dock as bottom overlay coverage, then listened only for dock class changes. Applying CSS changed the dock's size and position without changing its class, leaving a stale projection offset.

Correction: ignore unstyled static overlay boxes, refresh insets on the dock stylesheet's load, and observe both the dock wrapper and body with `ResizeObserver`. Keep the summary card outside these measurements so folding it cannot move the view. The regression starts fresh, delays the stylesheet, measures actual visible robot mesh bounds in screen space, and checks that stats folding preserves the projection matrix.

The first corrected WebKit run passed the bounds and interaction assertions but reported `ResizeObserver loop completed with undelivered notifications.` Synchronously resizing the canvas inside observer delivery can cause another layout delivery. Coalesce observer-triggered inset updates into the next animation frame instead; retain the page-error assertion so this warning cannot be silently accepted.

Final verification on 2026-10-29 UTC: `SITE_URL=http://127.0.0.1:8890 node tools/test-robot-controls.mjs` and `PLAYWRIGHT_BROWSERS_PATH=/tmp/gyropup-security-browsers PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8890 node tools/test-robot-controls.mjs` both reported PASS for fresh delayed-CSS startup framing, stable stats overlay, v1/v2 controls, and six phone/tablet layouts, with the page/stage error checks enabled. The fresh manual screenshots showed the complete current robot above the dock in both engines.

Rule: validate the first ready-state view with delayed optional UI styling, not only views after navigation, resize or model selection. See [Playground interactions](../domains/playground-interactions.md). This evidence covers the tested browser layouts; it does not certify every future overlay or physical device.


## 2026-11-11 — Retain the held stylesheet's actual request lifecycle

Normal CI run `43003806788`, source `7cd24223`, Playground job `130466178082`
failed the original 30-second stylesheet response wait after ready/talk and
held-CSS assertions passed. Artifact `13847059620` (SHA256
`40821a20b63b836449ca98cdbf70f229476b32bbc46ddd764fe67972b2548936`)
retained earlier availability evidence but no fresh-page request lifecycle.
The fixture was unchanged from dev2011; this does not establish a stylesheet
race, a GPU cause or why the response was absent.

Retire the completed availability page to `about:blank` after its origin-bound
saved-state clears, then run the unchanged fresh-context fixture. Reuse the
existing guarded acknowledgement with explicit base in both contexts, and
guard the harness probe init callback by intended HTTP origin. Actual VM
controls reject opaque/foreign storage access while preserving intended-origin
storage failures; keep the old unguarded historical helper bytes. Record only
owned talk.css route entry, stable request identity/count, release, continuation
outcome, response/failure and relevant navigation/errors. Expose replacement of
a still-held resolver rather than silently losing that request in evidence;
do not infer that multiple requests occurred in the original failure. Cap the
receipt at 64 events with dropped/count fields, sanitize URLs/text with the
existing diagnostic serializer, and write on pass/fail within two seconds.
Preserve the original error if evidence or cleanup fails; retain actual CSS
continuation, all geometry/overlay assertions and original response deadline.
Pure controls cover identities, redaction, caps and stalled/failed writes.
Actual new CI is still required; diagnostics are not a successful interaction.


### Review recurrence: observation did not establish owned cleanup

[Independent local-source BLOCK](https://github.com/Valpatel/gyropup/pull/315#issuecomment-6793958443)
at `648b9a91` executed the actual fresh-layout caller with two held CSS requests
and an original timeout. Context close ran, but only the newest request
continued; the older JavaScript gate remained pending. The twenty passing
controls had missed this because one control released that gate externally.
This was a demonstrated test-ownership defect, not proof of the original CI
response-timeout cause.

Keep the primary release unchanged, retain every owned releaser in a Set, and
drain the Set in actual cleanup. Observe all owned callbacks with bounded
`allSettled` before the final receipt, including routes entering during teardown.
A two-second cleanup fence bounds native continuation/context-close waits only
once teardown starts; it does not change the original response/readiness waits.
Record pending native commands or a pending/failed close as incomplete rather
than claiming termination. Preserve the identical original error across cleanup
and report failures. Actual-caller controls now own every gate themselves and
cover success, original failure, continuation rejection/stall, failed/stalled
close, late routes and report failure without external resolver access.
