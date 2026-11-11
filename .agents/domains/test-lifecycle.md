# Test-owned asynchronous resources

An assertion pass is incomplete until its test's sockets, tasks, threads and
event loops have finished. Retain ownership handles and use bounded waits that
fail visibly; daemon threads are not teardown.

For a coroutine submitted to a separate loop, await its completion before
stopping that loop. Keep the loop and transport valid until their reader has
joined. Closing a listener does not close accepted connections: close and await
each writer, even when cancellation interrupts an incomplete request.
Stop accepting first, finish connection handlers, then await server closure:
Python 3.12 includes accepted clients in that wait. Preserve resource cleanup
when a completed shutdown reports an error, and re-raise that error afterward.

Validate completion with held real resources, not retry-until-green runs. Put
observation outside the cancellation domain being tested; always release test
gates in `finally`. A pre-fix control should fail for premature return while the
fixed implementation leaves no owned work behind. Preserve behavioral guards.

Evidence: [RS-04 test shutdown](../inbox/2026-11-06-test-close-must-finish-owned-threads.md).


For full single-size CI layout jobs, use one owned page loop while retaining
matrix partitions and complete route/theme coverage. Retire completed independent
rendered pages before a fresh-context fixture; perform origin-bound storage edits
before navigating away. Keep bounded request lifecycle evidence and original
failure/deadline semantics. See [CI readiness scheduling and its limits](../inbox/2026-11-11-layout-readiness-failures-need-current-scene-state.md#2026-11-11--keep-full-ci-coverage-while-scheduling-one-page-loop-per-job)
and [held stylesheet evidence](../inbox/2026-10-29-late-overlay-styles-must-refresh-camera-insets.md#2026-11-11--retain-the-held-stylesheets-actual-request-lifecycle).
