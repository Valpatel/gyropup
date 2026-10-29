# Landing highlights reel

Issue [104](https://github.com/Valpatel/gyropup/issues/104) replaces the old
target-practice snapshot with a 22-second edit of current browser footage and
explicitly historical engineering studies. The public turret is the 48-part model
shared by the landing character and simulator; the Orin bench adds 18 enclosure
and adapter parts. The full-robot body remains an interim export. Current demo
movement is scripted browser motion with projectile integration, not a newly
solved whole-robot physics run.

| Time | Footage | Evidence boundary |
| --- | --- | --- |
| 0–4 s | Current turret close-up | Actual public CAD, with a camera orbit and aim change |
| 4–7 s | Feed and flywheel inspection | Actual simulator callbacks and emitted balls, transparent shells |
| 7–13 s | Target practice | Three actual projectile hits and three target knockdowns |
| 13–16 s | Isolated leg-rig jump | Archived MuJoCo study, 16.25 kg per leg, 48.1 V, 60 N·m cap |
| 16–19 s | Hip-frame E1 | Historical static load scaling, not transient dynamics |
| 19–22 s | Current robot | Current turret on the interim body, moving in the browser demo |

The leg movie belongs to the report at
`ae919f7211f236f398ff77cc25d00c2017c1ab9c`, not today's 18.75 kg / 36 V report.
E1 retains its 37.5 kg baseline, deformation ×77, SF 1.65 versus required 2.00,
and static-load labels. Its entire native frame is preserved with side bars;
the failed strength target is neither cropped nor covered. These are prototype
demonstrations, not physical testing or a print/safety release. The separate
Progress leg-gallery mismatch is tracked in
[issue 106](https://github.com/Valpatel/gyropup/issues/106).

## Capture and encode

Use Node 22, the pinned Playwright package, installed Chrome, and FFmpeg with
libx264, libvpx-vp9, libwebp and FreeType. Build and serve the repository first,
then capture its actual browser simulation:

```sh
npm run build
PORT=8899 node tools/serve-site.mjs
# In another shell:
SITE_URL=http://127.0.0.1:8899 node tools/capture-highlights.mjs
python3 tools/encode-highlights.py --frames /tmp/gyropup-highlights-frames
python3 tools/check-highlights.py --frames /tmp/gyropup-highlights-frames
```

The recorder exposes the existing stage callback array, stops its animation
loop, advances those callbacks at 60 Hz with a seeded random source and a fixed
performance clock, and explicitly renders 30 captured frames per second.
It does not replace model, feed, projectile or target code. Real PNG dimensions
must be 1280×720; the page header's usual canvas inset cannot change the raster.

The first release was captured from build `7b70f23f510c6b310cc8871b145cbe439f13312d`,
assets `114e495ece58fdcdacf2`. The receipt includes each loaded source's local
and served hashes, the exact callback-exposure transform, model identities,
per-frame observations, capture recipe and browser version. Original PNGs are
temporary; their hashes and dimensions are committed in `capture-frames.json`.
The recipe is reproducible, but GPU/browser/codec differences mean cross-host
byte-identical rendering is not promised.

`tools/encode-highlights.py` uses lossless intermediate segments, the repository's
Inter font, and two encodings of the same edit. Outputs live in `web/highlights/`:

- H.264 High 3.1, YUV420P, 720p30, fast-start MP4: 1,809,246 bytes.
- VP9 Profile 0, YUV420P, 720p30, WebM: 1,438,730 bytes.
- A WebP poster from reel frame 30, with the same framing and lower third.
- Source, edit, capture and output receipts, including the historical leg report.

Each movie contains 660 frames and no audio. The player fetches only its supported
encoding near the viewport, pauses offscreen or when the tab is hidden, and keeps
a deliberate user pause. Reduced-motion and Data Saver visitors start it manually.
The finite reel offers replay, clear loading/error states and retry; it works even
if the independent 3D hero fails.

## Validation

`npm run test:highlight-media` checks source/output identity, mandatory input
membership, historical report binding, codec/profile/raster/frame count, full
decode, MP4 atom order, transfer budgets, moving model pixels in every segment,
equivalent H.264/VP9 pixels, retained E1 labels and the matching poster. Fault
controls reject missing or changed sources, wrong historical baselines, incorrect
static labeling, changed output bytes and frozen frames. No CAD solver runs.

`npm run test:highlights` checks actual decoded moving pixels, MIME types, one
selected codec, initial and near-viewport requests, manual preferences, pause,
replay, visibility changes, a pause during a delayed response, HTTP 503/invalid
media recovery, keyboard controls and 13 phone/tablet/desktop viewports. Run it
with bundled Chromium, installed Chrome and WebKit; a codec capability query alone
is not a playback test. Both checks run in the existing presentation CI workflow.

Final browser and independent review results are recorded on
[PR 105](https://github.com/Valpatel/gyropup/pull/105). Production playback is checked
again after the reviewed dev/main publication.
