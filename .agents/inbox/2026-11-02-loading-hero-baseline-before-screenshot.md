# The loading-hero baseline was taken before its own screenshot

On 2026-11-02 UTC the required `browser-validation (loading, …)` job failed on unrelated PRs (#161, #162) and on a `main` push, while some re-runs of the same commits passed. `tools/test-loading-hero.mjs` failed in its "delayed entry" case at 844×390:

```text
assert.deepEqual(after.hero, before.hero)
- y: 30.390625, bottom: 514.390625
+ y: 10.390625, bottom: 494.390625   (x 448.4, w 367.6, h 484 unchanged)
```

Cause: the test measured `before`, then took the loading screenshot of `.hero-scene`, then released `landing.js`. The hero (484 px) is taller than the 390 px viewport, so Playwright captures it with Chromium's `captureBeyondViewport`. That briefly resizes the viewport (a page-side `resize` listener saw 1×1, then 844×390) and, when the renderer is slow enough to lay out the intermediate size, scroll anchoring leaves `scrollY` 20 px further down. The hero's document position never changed (230.39 px); only the scroll offset did, before the scene module was even released.

Evidence (local, Playwright 1.56.1 Chromium, with `Emulation.setCPUThrottlingRate` 6 to imitate a loaded runner):

- unthrottled: scrollY 200 → 200 across the element screenshot; the suite passes, which is why it failed only on CI;
- throttled: scrollY 200 → 220 across the screenshot alone, with `landing.js` still held; the unmodified test then fails with exactly the CI values above;
- throttled with scroll anchoring disabled (`overflow-anchor:none`), the same 1×1 resize still occurs but scrollY stays at 200, so scroll anchoring is what moves the page (independent review of #163);
- the corrected test passes throttled (baseline scroll 220, hero y 10.39 before and after) and unthrottled.

Correction: the same rule `tools/test-hero-preview.mjs` already follows ([earlier incident](2026-10-29-measure-handoff-after-font-and-capture-setup.md)). Font loading and the screenshot are setup; take the strict baseline after them and two rendered frames, while the module is still held. The test now also records the scroll offset and asserts it is unchanged by the scene load, so a page that scrolls itself is reported as such. Exact box equality is kept. A mutation that adds 60 px above the hero once the scene is ready still fails the test.

Limits: this does not prove the page never shifts under other timing, nor explain why runner load rose on that day. If a hero-jump assertion fails again, record `scrollY` and the hero's document position at each phase before blaming the page.
