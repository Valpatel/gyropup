# Complete a failed archive load cohort before exposing its retry

On 2026-11-11 UTC, main `d694b3aa` passed both current-model browser captures and
their shared geometry validators. A later legacy archive retry test failed with
`Robot mesh turret__tilt_12_flywheel_motor_l.stl: ... the connection failed`.
The test had deliberately aborted archived meshes, observed one rejection,
removed its interceptor, and immediately started another archive load.
The [failed job](https://github.com/Valpatel/gyropup/actions/runs/42938565751/job/130254586898)
and [80-member archive](https://github.com/Valpatel/gyropup/actions/runs/42938565751/artifacts/13820510865)
retain the original observations. The archive passed CRC with SHA256
`d07959b606a1dcad441759cc552547cce830e32846597c09618fb66d3ae9e514`.

The old loader used `Promise.all` for the archive mesh cohort and cleared its
top-level load promise on the first rejection. Sibling requests could remain
in its per-mesh pending map. An immediate caller retry could reuse a pending
sibling that later rejected from the earlier failed attempt.

The actual-module regression uses the real archived STL bytes and synthetic
staggered fetch failures. At dev `28b5b0fa`, the retry from the first error
handler failed with the same mesh message. The initial read-only source control
had SHA256 `c54eb7fc2915c80a92cea0f6876ccc83a41bc4b80840f424b4f02fc6ad8ad4b6`.
The new test fails the old implementation on the immediate-retry success
assertion and passes with the bounded cohort completion. Its separate disposal
control requires all held readers to observe the existing lifetime abort.

The archive loader now retains the first rejected mesh error and awaits all
siblings under the existing reader timeout before exposing that rejection.
Successful mesh caching and current-scene preservation remain in place.
Do not replace the retry assertion with a delay or forgive a second failure.
Dispose still aborts the existing reader signals. The regression command is
`node --test tests/site/models/test-archive-retry.mjs`.

The browser failure had no per-request trace, so its exact abort ordering remains
unproven. The deterministic loader defect is independently reproducible.
This change affects a captured media input and therefore requires a fresh
source-bound capture before media adoption. It establishes no physical or
manufacturing qualification.
