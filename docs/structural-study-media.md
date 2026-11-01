# Structural study media

The Progress page's hip-frame E1 movie is a **12-second presentation of a linear-static solution**, not a 12-second dynamics simulation. The clip scales one solved load from zero to its design value and back, exaggerates displacement 77 times, and slowly orbits the part. Cyan arrows depict the two resultant forces; the field also includes the six recorded moments, available in the interactive 3D viewer. Gray surfaces mark excluded idealized support/load patches; the faint gray outline is the unloaded shape. Stress colors span zero to the recorded 13.91 MPa design peak.

The existing strength failure is unchanged: **SF 1.65, required 2.00**, maximum displacement **0.2678 mm**, humid weak-direction PA6-CF. This is the recorded **37.5 kg** robot baseline (rounded to 38 kg in the existing load description). It does not validate the future 100 lb target, printing, assembly, fatigue, contact, preload, buckling, crack propagation, or operation around people. A smoother animation is not stronger hardware.

**Status, 2026-11-01:** this movie and its field are the record from before [PR 134](https://github.com/Valpatel/gyropup/pull/134) (issue 29), which changed the hip frame's flanges and the knee bearing. Studied at that PR's head, the new frame reads E1 SF 2.08 at the 4 mm gate and 1.81 at 3 mm, so the value is not converged against 2.00. Regenerating the full leg record and this movie with the pinned toolkit is the first next step in issue 29.

## Reproduction and provenance

The original summary was published in `2cb254fad8927dc71d8b2c80176c01d5ad0578d8` from `python cad/leg_studies.py --no-anim` at `c1dbc10`. It contains a PNG but no video or exported field. The relevant mechanical and load inputs are unchanged at the production base `c9229dd24d5616f28c010a22d81627e24e3bf065`.

`tools/export-hip-frame-e1.py` adds one bounded reproduction, using the same existing individual-part setup and existing whole-leg load shares. It requires committed default inputs, runs only hip-frame E1 at 4 mm P2 tetrahedra, compares the result with the original summary, and exports the solved surface to an isolated directory. It never overwrites the original summary. The successful producer revision is `831532a951ae55df4d1f09470382ba7779c71fa3`, with cad-agent v0.4.0 at `28abd34caf650ced78d9d734af000715ee174efe`. `field-receipt.json` records all source and toolkit Python hashes, runtime versions and mapped mesher/OpenSSL binary hashes. The surface has 20,936 vertices and 41,960 triangles; the mesh has 34,101 nodes and 146,362 tetrahedra. The reproduced PNG matches the original SHA-256 `69bef81914bd4103edfd2e7c1275747bbbe84ff1b5abd3c54dc8fa619feab5d3`.

Run CAD only on the isolated compute environment following the remote-run skill. Its manually installed mesher requires the matching crypto and SSL libraries in **process-local** `LD_PRELOAD` before Python starts; `hashlib` can load system OpenSSL before a later `import gmsh`. Do not change global linker settings or a shared environment. Paths and host mapping remain in private team configuration; the public receipt records binary identity, not private host details. The successful run and collect locations are tracked in [issue 69](https://github.com/Valpatel/gyropup/issues/69).

`tools/render-hip-frame-e1.py` needs NumPy, PyVista, Matplotlib and FFmpeg, but never imports a solver. At the recorded renderer revision, run:

```bash
python tools/render-hip-frame-e1.py
```

It reads the committed solved field, verifies its receipt and baseline binding, renders 288 frames at 24 fps, and writes H.264/yuv420p MP4, a VP9/WebM companion, poster, timeline and `video-receipt.json`. Each frame explicitly redraws the VTK framebuffer before capture. The media index binds the video and interactive field to the report's case, strength numbers, displacement, stress and load description. Historical CAD hashes are compared with the **producer revision**; this does not claim that a future mechanical revision is represented by this older study. Current report, rendering source, fields and output bytes must still match their receipts.

## Validation

```bash
python3 tools/check-study-media.py
python3 tools/test-study-media.py
SITE_URL=http://127.0.0.1:8899 node tools/test-study-media.mjs
PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8899 node tools/test-study-media.mjs
```

The source/artifact checker verifies historical source blobs, current report identity, field dimensions/units and physical displacement, complete input/output hashes, bounded load timeline, codec, duration and all 288 decoded frames. It independently compares the model region in unloaded and loaded frames with the same camera direction, excluding captions. The shipped loop changes 29.61% of sampled color channels by more than 20 levels, with mean absolute difference 29.83/255. A frozen-frame negative control must fail; a 12-second container alone is insufficient. Twelve artifact/metadata mutations must also fail.

The browser harness exercises real decoded playback, pause, keyboard controls, reduced motion, muted autoplay, 320×568, 390×844, 844×390 and 1440×900 layouts, actual 3D field rendering, missing clips, HTTP503, invalid media, retry, case switching during a held request and stale result identity. Installed Google Chrome, pinned Playwright Chromium (the CI engine) and WebKit pass. The player chooses AVC High level 3.1 when supported and the VP9 companion otherwise; both encodings are fully decoded and compared against the same model-region samples. The mean inter-codec pixel difference is 0.83/255. Browser tests use an isolated pinned Playwright cache to avoid other worktrees garbage-collecting a required browser version. Markdown reuses the published player adapter and preserves the watch link and scientific limits.

Reports without published clips show their still image with an explicit explanation. Failed clips retain the report and still with a retry action. Neither state displays a zero-second player. These checks establish presentation and artifact integrity; they do not independently validate the mechanical model or qualify the part for manufacture.
