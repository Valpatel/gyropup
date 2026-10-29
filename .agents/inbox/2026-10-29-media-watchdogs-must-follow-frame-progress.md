# Media watchdogs must recognize actual frame progress

On 2026-10-29, extending the native WebKit replay beyond a short success probe
found a false recovery timeout in PR112. A fresh context used the actual hero
and movie, with no request interception or media-property overrides.

The retained `webkit-full-replay-trace.json` from build `896422a` records:

```text
time=18.006 s, frames=541, paused=false, readyState=2, UI=buffering
time=19.006 s, frames=571, paused=false, readyState=2, UI=buffering
time=19.991 s, frames=599, paused=true,  readyState=2, UI=error
ended=false
```

The player relied on another `playing` event to clear its 20-second waiting
timer. WebKit kept presenting frames without that event, so the watchdog stopped
a working replay. A one-second replay check had missed the later failure.

Recognize actual forward frame progress while playback is eligible, not paused
or seeking. Bind recovery callbacks and their baselines to the current source and
play attempt; invalidate them on cancellation, retry and replay. A stale frame or
seek must not clear a new attempt's watchdog, and deliberately paused refill must
retain its buffer requirement. Truly frozen recovery still needs a timeout.

Complete the entire second replay, including the watchdog boundary. This is
browser playback evidence, not a change to video content or a claim that every
device dispatches identical media events.
