# Virtual-clock fixtures need their own browser contexts

On 2026-10-29, the final WebKit player suite reached 20 product cases on the
immutable `e1ed8e7` preview, then failed while installing the second virtual clock:

```text
PLAYWRIGHT_BROWSER=webkit SITE_URL=https://3e048b75.gyropup.pages.dev \
  node tools/test-highlight-video.mjs
clock.install: TypeError: undefined is not an object (evaluating 'globalThis.__pwClock.controller')
```

The failure happened inside `page.clock.install()` before the frozen-recovery
fixture navigated to the page. The first clock fixture had closed only its Page;
its BrowserContext was reused by later cases. Playwright's clock instrumentation
is context-scoped, so another Page did not isolate the virtual-time state.

Give each virtual-clock fixture a fresh BrowserContext, install the same normal
preferences there, and close that owned context after the case. Keep browser
teardown in `finally` for failures. Do not interpret an automation setup failure
as a product pass, remove the watchdog assertion, or change working player code
to accommodate a leaking test clock. Re-run the failed browser suite on the same
immutable product build to distinguish a harness correction from a product fix.

This incident concerns the pinned Playwright/WebKit combination. It does not
claim that all failures involving clocks have the same cause or that a real
browser's timers were defective. Regression: the hung-hero and frozen-recovery
cases in `tools/test-highlight-video.mjs` both retain their original assertions.
