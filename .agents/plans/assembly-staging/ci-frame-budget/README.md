# Separate actual simulation completion from static-fixture and observer failures

[Investigation/source identities](investigation.json) preserve both original CI
failures. The gamepad failure had an unfinished recovery at jump.t1.35/y0; exact
frame/paused/error history was not recorded. The WebKit guide job completed all15
groups before its strict error list rejected the unsupported localhost changes
poller. Neither original failure is relabelled as a passing run.

The landing test explicitly replaces its old generic15s wall default with3s
summed actual stage callback dt,30s hard wall and10s no-frame caps. Actual input,
start and>0.12m airborne checks retain their15s guards. Paused/hidden/replay/error
states and late completion reject. The helper contains no trajectory and resets
no product hop state. This is a test contract, not a product responsiveness or
physical-motion specification. See the [canonical lesson](../../../inbox/2026-11-10-hop-completion-needs-the-actual-stage-clock.md).

The [genuine gated control](hop-gated-accepted.json) uses actual gamepad input and
existing stage callbacks with an explicit1000ms rAF delay. It fails the old15s
predicate yet genuinely reaches jump=null/y0 within20.667 wall/1.4373 stage-dt
seconds under the corrected synchronous guard, without releasing the gate to
force success. The [fresh actualstage.stop control](hop-stopped-rejected.json)
is rejected after10.022s without a frame while the jump remains active. Ordinary
controls also reject continuing frames with no completion, wall excess and
invalid/paused/hidden/error observations. NativeChrome151 is explicitly distinct
from CI's bundled Chromium.

The [normal full-gamepad hop](gamepad-hop.json) finishes in1.45 stage-dt seconds
and29 actual frames; all following unchanged gamepad assertions pass. The full
[WebKit guide suite](guide-webkit-passed.json) passes15groups with zero pageerrors
and zero unsupported-development requests. Every browser error remains enforced;
only static loopback contexts use the shared component's existing marker, as
proven by [actual positive/negative contract controls](static-poller-control.json).
Original WebKit error timing was not captured and is not inferred from that probe.

[Rejected observer attempts](rejected-observers/README.md) remain visibly INVALID.
The frozen geometry and a following unchanged assertion exposed an async
Promise-false acceptance. The corrected direct Playwright adapter is synchronous,
unit-tests both false/true returns and rejects Promise-valued guards, using the
same pure functions through handles created after scene readiness. The subsequent
wrong-context private setup made no valid guard query; it is not a product result.

[Accepted source/results](accepted-results.json) bind the actual staged helper,
harness and receipt bytes. Built source remains parent02d7 with test-only edits,
not a later immutable commit. Original runtime/player/CAD/poster inputs are
unchanged; no native CAD query or new assembly qualification occurred. Final
review/normalCI and any subsequent cumulative-runtime composition still require
their own exact-head checks. The [checkpoint](checkpoint.json) seals these records.
