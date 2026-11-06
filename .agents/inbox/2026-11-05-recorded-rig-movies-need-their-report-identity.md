# Recorded movies need their actual report identity

On 2026-11-05, the Progress leg gallery constructed `rig_<scenario>.mp4` URLs
from the current report. A newer report with the same scenario names would show
older movies without detecting the mismatch. Issue #106 had left this consumer
check unfinished even though its timeline and document corrections had landed.

Evidence: `node tools/rig-media.mjs --record
e7b512870a39259a04a4930e2908af84001bc84e`, followed by
`node tools/rig-media.mjs --check`, reported `Verified report and all 7 movies
against producer e7b512870a39259a04a4930e2908af84001bc84e.` The report SHA-256
was `171a1d4f2195468a235313fce29e5dde1272499b0d0934e22ad2bab5564ba902`.
The command compares the report and every movie with immutable Git blobs before
writing the receipt; it does not regenerate or reseal changed movie bytes.

Bind this small gallery to `exports/leg/rig-media.json`. The published browser
and Markdown renderer share `designer/rig-media.js`: exact report digest, fixed
paths, complete scenario membership and each actual movie digest must agree.
Browser playback uses Blob URLs made from the verified bytes; Markdown keeps
original downloads. Report values label the recording, not a duplicated budget.
Missing or mismatched media leaves numerical results visible with an explanation.
Retries revoke old URLs, and an older asynchronous result cannot replace a newer
state. Refine the existing Progress and Markdown harnesses with wrong-report,
wrong-video, missing-receipt and stale-retry controls.

The exact bundled Chromium playback check subsequently exposed the known AVC
codec limitation: installed Chrome and WebKit played the original High31 clips,
while bundled Chromium rejected them. Follow the [codec lesson](2026-10-29-chrome-and-chromium-do-not-share-video-codecs.md),
preserve the originals, and derive lossless VP9 companions. Conversion provenance
records the committed converter, exact arguments and FFmpeg version separately
from the original e7 producer. Compare every decoded YUV420P and interpreted RGB24
frame, dimensions, frame count, colour metadata and ordered timestamps. WebM's
millisecond timebase permits at most 1.001 ms timestamp/duration rounding.

Independent review of `2e62ef4` found that correct frame timestamps do not prove
correct container duration. A 20-frame 2-second fixture with only WebM Duration
changed to 20 seconds passed. `370540a` probes actual format/stream duration and
rejects that same counterexample. Fleet173 on cpu-b passed all 675 original and
companion frames, plus honestly rehashed different-scenario, frozen-frame and
false-duration controls. This was conversion evidence, not a new simulation.

Cross-platform rechecking of that receipt found the YUV sequence digest and every
other field identical, but the recorded RGB conversion fingerprint differed
between ARM and x86 (`585c0a…` versus `ac8535…` for stand_up). Fresh original versus
companion RGB equality passed on both. The portable receipt therefore keeps the
canonical YUV sequence digest; every host still freshly compares each pair of RGB
frames, without treating a stored swscale conversion fingerprint as portable.
No pixel or timing comparison is removed. Regenerate receipts using the corrected
committed converter; never relabel old conversion provenance.

Limits: matching retained bytes establishes the report/movie relationship, not
the physical accuracy of the simulation or a hardware qualification. Large media
needs a separate loading design; the seven original MP4s total about 345 kB and
their lossless VP9 companions about 7 MB. Select the codec once before fetching,
verify that selected representation and pass the choice to playback; do not make
AVC-capable phones download both. Publication/Markdown checks still verify both.
The receipt is not a signature or a substitute for independent source review.
