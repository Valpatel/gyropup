# Media waiting can mean seeking or decoding, not missing bytes

On 2026-10-29, the first priority/buffering implementation in PR112 passed cold
Chrome network integration but broke native WebKit replay. The new `waiting`
handler paused unconditionally, invalidating the play attempt during seeking.

The native event trace from immutable build `61503da` showed:

```text
Replay: buffered TimeRanges remains [0,22]
waiting: readyState=2, currentTime≈0.0016, media.error=null
handler pauses; progress/play repeats the pause
20-second media timer expires
```

The file was already buffered. A network-readiness gate was being applied to a
decoder transition, and its own pause prevented native recovery.

Only enforce refill pauses when the contiguous buffer at the current playback
time is actually insufficient. Let native seek/decode recovery proceed when the
bytes are already available, retaining a bounded error path for genuinely stuck
recovery. Keep an actual native WebKit replay in the regression suite; fabricated
buffer ranges alone do not exercise this browser behavior.

This is a player lifecycle correction, not proof of HTTP byte-range support or
a fix to Cloudflare caching. The media files and codecs were unchanged.
