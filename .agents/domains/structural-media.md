# Structural media and recorded evidence

Use `designer/kit/study-media.js` for report stills and clips. A missing clip is a still with an explicit unpublished-animation note; a failed clip keeps the report and image, exposes retry, and never shows zero-second native controls. Each selection invalidates previous events and timeouts. Reduced-motion users start playback deliberately. Preserve the same state semantics in agent Markdown using the published module's static adapter.

For static FEA, label animation as static deformation/load scaling, never as physical elapsed time or crack propagation. Preserve failed strength targets, real displacement, material assumptions and the historical load baseline. Keep exaggeration separate from physical units and do not silently apply an old study to a changed design. An attractive clip is not manufacture or safety qualification.

Bind a field to committed producer inputs and a report, and bind a video to that field, renderer and output bytes. Validate actual mapped mesher libraries and toolkit sources. Historical input hashes are checked at the producer Git revision; current report and output identities must match their receipt. `tools/check-study-media.py` and `tools/test-study-media.py` check source identity, scalar/geometry layout, bounded load timeline, decoded duration/count and an independent image region with a frozen-frame negative control. A valid video container can contain a frozen framebuffer; explicitly redraw before every capture.

`tools/test-study-media.mjs` checks real advancing decoded frames, keyboard and phone controls, reduced motion, case-switch cancellation, missing clips, HTTP503/invalid media, recovery, stale report identity and the corresponding interactive field. Use both Chromium and WebKit. See [reproduction and limits](../../docs/structural-study-media.md) and [the framebuffer incident](../inbox/2026-10-29-video-duration-does-not-prove-a-moving-simulation.md).

Installed Chrome and bundled Playwright Chromium can have different codec support. Test the exact CI browser as well as Chrome and WebKit; inspect `canPlayType`, media errors and ready/network state rather than extending timeouts. The E1 player uses H.264 when its actual AVC profile/level is supported and the source-bound VP9 companion otherwise. Both encodings require full decode, equivalent model-region pixels and correct media MIME types. See [the codec incident](../inbox/2026-10-29-chrome-and-chromium-do-not-share-video-codecs.md).

An adjacent report can be newer than its movie. Bind each clip to the report and
producer revision that actually created it; label archival inserts independently
of the current model. The landing highlights recipe and checks are in
[the reel validation record](../../docs/validation/landing-highlights.md). Check
the actual captured raster dimensions, not only the viewport or requested size:
page headers, resize observers and camera inset updates can resize the framebuffer.
Read the PNG dimensions before encoding so a 1280×656 canvas cannot be silently
stretched into a claimed 1280×720 capture.

Validate replay and seeking after initial playback. The local preview server must
serve real single byte ranges, as a media client can reject HTTP 200 when resuming
with a range. `tools/test-site-ranges.mjs` checks HTTP semantics and the highlights
browser harness checks the consumer. Verify production range responses separately.

Exercise the real 3D hero and movie together on a constrained connection. An
isolated player's successful first decoded frame does not prove smooth playback
or that competing CAD downloads meet their deadlines. Check automatic and
explicit loading order, queued-play cancellation, failed/missing hero release,
initial buffering, and an actual network-emulated integrated page. Keep those
observations distinct from real-device performance guarantees.

Before a delayed media request or play attempt, verify current bounds as well as
observer state; a scroll can precede IntersectionObserver delivery. Keep queued
intent cancellation independent of an already-false visibility predicate. Native
`waiting` events can represent seek/decode with a complete buffer: inspect the
contiguous range before pausing, and retain native WebKit replay coverage in
addition to synthetic buffer tests.

Clear a recovery watchdog on actual forward presented-frame progress as well as
normal media events. Scope callbacks to the current play/source generation, and
invalidate them on cancellation, retry, seek and replay; frozen recovery must
still time out. Complete the full second replay past the watchdog deadline.
Read current reduced-motion preferences at the final eligibility decision:
WebKit can briefly report a fresh query as true before a retained list and its
change listener update. Keep the listener for ongoing cancellation too.

Validate the visible and accessible controls in every playback state. The primary
control owns Play/Pause/Replay/Retry; Restart is a distinct unfinished-playback
action and disappears when unavailable. Preserve focus when that action vanishes,
and assert exactly one Replay after both natural ends. Decoding and recovery
checks alone will not detect duplicated actions. See [the player-control incident](../inbox/2026-10-30-player-actions-need-distinct-state-ownership.md)
and `tools/highlight-control-contract.mjs`.
