# A fixed sleep does not prove a wheel-zoom frame was rendered

On 2026-10-29 UTC, PR51's mechanism CI failed at `tools/test-camera-controls.mjs:53`: “One-pixel trackpad motion remains fine-grained.” The camera source was unchanged by the latest documentation-only commit. The test sampled after 900 ms, although its larger-wheel test already sampled actual animation frames.

The CI log did not record the sampled radius, so its exact scheduling history is unknown. A controlled Chromium probe reproduced the false-failure class by holding animation callbacks for 950 ms after a one-pixel wheel event:

```text
held radius: 1.9999999999999998, queued animation callbacks: 1
after callbacks resumed: 2.0002502656854593
expected radius: 2.0002564829164036
```

The correction waits for the mathematically expected eased radius with the existing bounded `reaches()` helper before taking the fine/notch samples. It retains the original increment bounds, immediate-jump prohibition, monotonic intermediate-frame check and native gesture tests. Both complete Chromium and WebKit camera suites then passed. No camera implementation or zoom sensitivity was changed.

Use state/frame predicates for render-dependent observations. A wall-clock delay may allow zero frames on a busy software renderer. Keep failure diagnostics numeric, and do not label every timing-related CI failure a product defect or rerun it away without examining the predicate.
