# RS-04 runtime ownership

`rig.rs04_bridge.serve()` owns its listener, accepted connections, WebSocket
sender/watchdog tasks, transport reader and transport. It borrows the caller's
event loop. Retain handles when resources are created, including synchronous
registration of accepted writers before their handler's first coroutine step.

On cancellation or startup failure, stop accepting and send STOP before awaiting
cleanup. Finish owned handlers and their child tasks, join the reader with a
bounded wait while its loop/transport remain valid, close the transport and then
await server closure. Python 3.12 server closure includes accepted connections;
do not place that wait ahead of their cleanup. A receive that exceeds its join
bound is a shutdown failure even if closing the transport later wakes it.

Never blanket-cancel tasks on a borrowed loop. Preserve errors after releasing
resources. `main()` handles pre-runtime construction failures separately and
must not report a successful exit with an owned reader still running.

Validate the real production entry points on Python 3.10 and 3.12 using software
motors. Hold genuine reader/child work, exercise partial requests and startup
failure, keep a caller task alive, and check the pre-fix control fails. Test-helper
teardown alone is not production evidence. These checks do not replace hardware
qualification or physical stop measurements.

Evidence: [production shutdown incident](../inbox/2026-11-06-runtime-shutdown-must-finish-before-loop-closure.md).
