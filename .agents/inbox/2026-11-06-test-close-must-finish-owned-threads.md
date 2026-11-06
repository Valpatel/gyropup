# A test close must finish its owned threads before returning

2026-11-06 UTC, #225: the Python 3.10 deploy check passed all 13 bridge/vector
tests, then aborted with `_enter_buffered_busy` on stdout during interpreter
shutdown (run 42132601914). The successful assertions did not prove teardown.

Local command: `python3.10 -m unittest rig.tests.test_rs04_vectors
rig.tests.test_rs04_bridge -v`. Baseline output: `Ran 13 tests in 1.734s / OK`.
A bounded event gate then held the real websocket handler's `tab disconnected`
log on software motors. The actual `Server.close()` returned in 0.026 ms while
that log was unfinished, its loop was running and two owned daemon threads were
alive. The diagnostic released its gate, joined those exact threads and closed
its own loop. Independent review reproduced the same path at 0.018 ms.

Cause: the test helper discarded the shutdown future, retained no thread
handles, and never closed the loop. Closing the listener also did not establish
that accepted sockets or the transport reader had finished. No hardware was
connected or commanded.

Correction: await the shutdown coroutine while its loop is running; close and
await accepted writers, including incomplete HTTP requests; join the reader
before closing its transport; then stop, join and close the loop. Bounded waits
fail visibly. Successful close is idempotent. Unexpected cleanup exceptions
must propagate, rather than becoming a successful teardown.

The existing bridge harness now holds the actual disconnect finalizer and
transport receive call behind separate event gates. Both controls reject the
original published `Server.close` method with `TimeoutError not raised`: it
returned before the held resource finished. Positive checks require closed
sockets/listener/loop and no owned threads or pending tasks. The initial reader
control accidentally scheduled its observation on the loop being cancelled;
it now observes the listener from outside that cancellation domain.

Cross-version validation and independent review caught a real ordering error in
the first fix: Python 3.10 passed, but Python 3.12's `Server.wait_closed()` waited
for still-open clients before the helper cancelled them. An unmodified live
websocket reproduced the five-second timeout. Stop accepting first, cancel and
finish connection handlers next, then await the server's completed closure.
Completed shutdown errors still require thread/transport/loop cleanup before
being re-raised. A timed-out, incomplete shutdown must not be marked closed.

Limits: this reproduces premature test teardown, not the exact low-level stdout
lock crash. Production bridge shutdown, physical motor behavior and hardware
qualification are outside this change. Existing bus guards, origin/token rules
and stop-on-disconnect/quiet assertions remain intact. See the
[test lifecycle rule](../domains/test-lifecycle.md).
