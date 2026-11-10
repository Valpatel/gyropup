# Keep failed observer attempts rejected

These are investigation records, not passing product evidence. The first async
Playwright predicate returned a Promise from an exposed Node guard. That Promise
was truth-tested before its false resolution. The actual stopped stage retained
jump.t0.5, y0.143 and11 frames while the observer falsely accepted. The full
unchanged following gamepad assertion independently rejected jump.t0.65 instead
of null. The apparent gated newPass and all acceptance claims from that observer
are INVALID. Its second-hop precondition failed because the first hop had not
actually completed, not because a genuine new hop froze.

The synchronous private control initially created function JSHandles before
navigation; that navigation invalidated them. It made no valid guard query and
its pending old observer errored during cleanup. The main harness creates handles
after scene readiness. Preserve this setup failure and explicit listener closure;
do not silently replace it with a later control.

The corrected adapter is synchronous, passed directly to Playwright, and calls
the exact pure guard/read-sample functions through same-document handles. It
rejects Promise-valued guard results. Genuine gated completion and a true
stopped-stage rejection remain required before qualification.
