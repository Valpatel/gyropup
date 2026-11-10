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

## Manual playback tests must observe the action they activate

2026-11-10: the final integration run at `066b79f9` passed unthrottled automatic
playback and the shaped cold-manual recovery, but the normal manual case waited
90 seconds after cancelling its own queued playback. The retained report from
[job 130206301733](https://github.com/Valpatel/gyropup/actions/runs/42924146130/job/130206301733)
shows `manualBeforeClick.video.state = queued` at 565.3 ms and
`manualAfterClick.video.state = paused` at 853.6 ms. The hero became ready at
1797.7 ms; there were no movie requests, page errors or failed requests. Artifact
13812719300 has SHA-256
`0761c29d5168e2955c65845bf520234c896df24ec56f9c1c3bd054eae9899588`.

The harness waited 150 ms, read the button label, and conditionally cancelled
autoplay before issuing a generic toggle click. The viewport observer could
queue automatic playback between the label read and the click. The product
correctly treated that click as Pause; the harness incorrectly expected Play.

Resolve the real `Pause highlights` action, cancel it, and observe the paused
state and `Play highlights` action before explicitly playing. Keep normal motion
preferences, actual media and model requests, full 22-second playback/replay,
decoded-frame and stall checks, and the existing case deadlines. This corrects
the test's intent ordering; it does not fix or waive the cold-start payload in
#299, and a source edit alone is not a successful browser campaign.
