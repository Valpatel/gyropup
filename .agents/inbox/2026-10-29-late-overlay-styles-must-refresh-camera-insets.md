# Late overlay styles must refresh camera insets before claiming startup framing works

On 2026-10-29 UTC, a fresh manual playground opened with its head and body clipped above the toolbar, although tests that switched models on an existing page passed.

Evidence at 03:15 UTC: a Chrome/SwiftShader browser at 1280×900 opened `/designer/sim.html?run=none&demo=0&sound=0` in a fresh context. A Playwright route held `character/talk.css` until `document.body.dataset.ready === '1'`, then released it. Before CSS, the talk body occupied `{top:68,width:1280,height:101.58}`; after CSS it occupied `{top:623,width:420,height:124}`. The camera retained `offsetY:396` in its 836px canvas after both measurements. The corresponding fresh screenshot showed only the legs below the toolbar. The reproduction command was `node /tmp/gyropup-fresh-layout-probe.mjs`; its deterministic route-hold sequence is now retained in `tools/test-robot-controls.mjs`.

Cause: `mountTalk` injects its stylesheet asynchronously. The simulator measured the unstyled normal-flow dock as bottom overlay coverage, then listened only for dock class changes. Applying CSS changed the dock's size and position without changing its class, leaving a stale projection offset.

Correction: ignore unstyled static overlay boxes, refresh insets on the dock stylesheet's load, and observe both the dock wrapper and body with `ResizeObserver`. Keep the summary card outside these measurements so folding it cannot move the view. The regression starts fresh, delays the stylesheet, measures actual visible robot mesh bounds in screen space, and checks that stats folding preserves the projection matrix.

The first corrected WebKit run passed the bounds and interaction assertions but reported `ResizeObserver loop completed with undelivered notifications.` Synchronously resizing the canvas inside observer delivery can cause another layout delivery. Coalesce observer-triggered inset updates into the next animation frame instead; retain the page-error assertion so this warning cannot be silently accepted.

Final verification on 2026-10-29 UTC: `SITE_URL=http://127.0.0.1:8890 node tools/test-robot-controls.mjs` and `PLAYWRIGHT_BROWSERS_PATH=/tmp/gyropup-security-browsers PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8890 node tools/test-robot-controls.mjs` both reported PASS for fresh delayed-CSS startup framing, stable stats overlay, v1/v2 controls, and six phone/tablet layouts, with the page/stage error checks enabled. The fresh manual screenshots showed the complete current robot above the dock in both engines.

Rule: validate the first ready-state view with delayed optional UI styling, not only views after navigation, resize or model selection. See [Playground interactions](../domains/playground-interactions.md). This evidence covers the tested browser layouts; it does not certify every future overlay or physical device.
