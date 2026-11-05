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

Limits: matching retained bytes establishes the report/movie relationship, not
the physical accuracy of the simulation or a hardware qualification. Large media
needs a separate loading design; these seven retained clips total about 345 kB.
The receipt is not a signature or a substitute for independent source review.
