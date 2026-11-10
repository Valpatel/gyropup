# Test cold reel override separately from full playback

On 2026-11-10, [PR #287 run 42917775368](https://github.com/Valpatel/gyropup/actions/runs/42917775368/job/130184737872)
used Chromium 141 with 150 ms latency and 200,000 bytes per second download.
At 91.275 seconds the hero remained loading, the reel was delayed and paused,
and there was no movie request, canvas, decoded frame, page error or HTTP error.
The [actual report](https://github.com/Valpatel/gyropup/actions/runs/42917775368/artifacts/13809369636)
records 175 completed current mesh responses and 14,478,800 encoded and decoded
bytes. The original browser outcome stays failed.

The 224 bound meshes total 17,350,766 bytes. At that throughput, they need at
least 86.754 seconds before considering other traffic, latency, parsing and
drawing. The player deliberately ends its wait after 60 seconds and offers
Play now. The original 90-second assertion expected automatic playback after
that intent had expired. The synthetic hung-hero test already verifies that
expiry does not silently start a competing download.

Keep full automatic and manual playback, source ordering, buffering, real
decoded motion and complete replay in the unthrottled integration. On the
shaped connection require the real queue, expiry and absence of a movie
request, then verify that explicit Play now starts a single movie encoding
with progressing decoded pixels while the hero continues loading or becomes
ready. Retain the 90-second action waits, 120-second case budget and current
mesh request diagnostics. [Issue #299](https://github.com/Valpatel/gyropup/issues/299)
tracks the measured startup cost separately from this harness correction.

The separate WebKit media partition runs actual hero poster parity, the
highlights player and both unthrottled integration cases. The existing
presentation aggregate requires that partition along with the Chromium suites.
