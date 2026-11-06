# Finish production shutdown while its event loop and transport still exist

On 2026-11-06 UTC, the independently reviewed test-server cleanup in #225
prompted a separate inspection of production `rig.rs04_bridge.serve()` and
`main()` (#227). Fixing a test helper did not prove production lifecycle behavior.

## Evidence

The original source at `bd95fb6d930a02a9fa4fde57a84e48d17a99cd4e` started
a daemon reader without retaining/joining it. `main()` performed its cleanup
after `asyncio.run()` had closed the loop. A software-only probe held the actual
virtual transport's `recv`, waited for the real listener, then sent SIGINT to
its own process running `main(['--iface', 'emu', '--emu-ids', '127', '--port', '0'])`:

```text
main_return=0 runtime_loop_closed=true bridge_running=false
transport_close_called=true reader_still_alive=1 reader_gate_unfinished=true
daemon_flags=[true]
```

The probe released its gate and joined its own resources afterward. This proves
premature completion; it does not establish a fatal interpreter error, an
actual closed-loop callback, a failed physical STOP, or any hardware result.

The first corrective candidate passed Python 3.10 but failed the held live
WebSocket test on Python 3.12. `Server.serve_forever()` handles cancellation by
closing and awaiting its server; on 3.12 that wait includes accepted clients.
The bridge's outer `finally` could not close those clients until that wait
finished. `asyncio.start_server()` already accepts connections, so the bridge
now waits for cancellation itself and owns the cleanup ordering.

Final focused commands on both interpreters:

```sh
python3.10 -W error::ResourceWarning -m unittest rig.tests.test_rs04_vectors rig.tests.test_rs04_bridge -v
python3.12 -W error::ResourceWarning -m unittest rig.tests.test_rs04_vectors rig.tests.test_rs04_bridge -v
```

Each ran 25 tests successfully (2.7 seconds). The added checks use the production
server, real software transport, actual sockets, a real SIGINT in a child
process, held reader/watchdog work, bind/ready/initialization failures, a bounded
reader-timeout failure and an unrelated caller task. The original production
`serve` restored from the immutable revision above fails all three selected
reader/bind/ready ownership checks. Diagnostic teardown joins each test reader.

## Corrective rule and limits

Retain only resources owned by this server. Stop accepting, send STOP while the
transport is valid, finish accepted connections and their child tasks, join the
reader with a bounded wait, then close the transport. Wait for server closure
after its clients. Report incomplete cleanup as failure. Preserve the caller's
loop and unrelated tasks; do not cancel `asyncio.all_tasks()` in production.

The outer entry point owns only resources created before the runtime starts;
it must not repeat runtime cleanup after loop closure. A daemon flag is not a
completion check. Software evidence does not qualify motors, mechanical parts,
bus wiring, physical stop timing or bench operation.

See [runtime ownership](../domains/rs04-runtime-lifecycle.md) and the separate
[test-helper incident](2026-11-06-test-close-must-finish-owned-threads.md).
