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

Corrective rule: await the stylesheets selecting the computed fonts, explicitly
load actual rendered text fonts/characters under a 30-second bound, then retain
the existing settling and media checks. This one harness sets Playwright's pinned
PW_TEST_SCREENSHOT_NO_FONTS_READY flag to avoid only the duplicate global wait.
No browser FontFace state is forged. Opaque/unavailable stylesheet or font errors
remain failures, not successful measurements.

Controls use the actual load/audit helpers: a held small image remains pending
while measurement completes; a held large on-screen image is rejected as never
loaded; an actual Inter stylesheet/font is held, then decoded before measurement.
Existing planted blank image/canvas, missing image, gap and squeezed-column checks
still reject in both themes. Pixel/media thresholds and two-frame settling are
unchanged. The held-resource control fails if an SDK upgrade removes the flag.

Limits: the control demonstrates the failure class, not the identity of the old
CI request. Core model/report readiness remains required. A timeout is never
counted as a measured view. This is a product-specific layout harness, not a new
network availability or universal font-rendering guarantee.
