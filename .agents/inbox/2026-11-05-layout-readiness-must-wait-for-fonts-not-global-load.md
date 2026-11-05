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
