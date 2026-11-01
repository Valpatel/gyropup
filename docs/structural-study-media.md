# Structural study media

The Progress page's hip-frame E1 movie is a **12-second presentation of a linear-static solution**, not a 12-second dynamics simulation. The clip scales one solved load from zero to its design value and back, exaggerates displacement 16 times, and slowly orbits the part. Cyan arrows depict the two resultant forces; the field also includes the six recorded moments, available in the interactive 3D viewer. Gray surfaces mark excluded idealized support/load patches; the faint gray outline is the unloaded shape. Stress colors span zero to the recorded 11.13 MPa design peak.

The strength gate fails: **SF 1.63 at the 4 mm gate mesh (1.41 at 3 mm), required 2.00**, maximum displacement **1.3117 mm**, humid weak-direction PA6-CF on cad-agent v0.6.0's data (18.13 MPa, E 488 MPa). The value moves by 13 % between 4 and 3 mm, so it is not converged; both are on the movie's caption. This is the recorded **37.5 kg** robot baseline (rounded to 38 kg in the existing load description). It does not validate the future 100 lb target, printing, assembly, fatigue, contact, preload, buckling, crack propagation, or operation around people. A smoother animation is not stronger hardware.

**Status, 2026-11-01:** regenerated for [PR 135](https://github.com/Valpatel/gyropup/pull/135) (issue 29) from the leg record re-run on cad-agent v0.6.0 at `d794466`, which includes [PR 134](https://github.com/Valpatel/gyropup/pull/134)'s hip frame and knee bearing. PR 134's own study read this frame's E1 at 2.08 at the 4 mm gate and 1.81 at 3 mm; those numbers came from cad-agent a682668, whose PA6-CF data predate v0.6.0. On v0.6.0 the same frame reads 1.63 and 1.41. The previous movie, from before PR 134 (SF 1.65 on cad-agent v0.4.0 data), is in Git history at `cb1149d`.

## Reproduction and provenance

The summary was regenerated for PR 135 from `python cad/leg_studies.py --mesh 4 --no-anim` at `d794466` with cad-agent v0.6.0 (`50d4921`), on the recording mechanical compute host (aarch64, conda-forge gmsh 4.15.2). It contains PNGs but no video or exported field. Its run provenance and the comparison with the previous record are in `research/fea-v060-29/`.

`tools/export-hip-frame-e1.py` adds one bounded reproduction, using the same existing individual-part setup and existing whole-leg load shares. It requires committed default inputs, runs only hip-frame E1 at 4 mm P2 tetrahedra, compares the result with the original summary, and exports the solved surface to an isolated directory. It never overwrites the original summary. The successful producer revision is `7f0dc67a54f78c029ae04beb0cd96915cda4e733`, with cad-agent v0.6.0 at `50d4921a5ab26c7750a869ed41c9a4346ef1379c`. `field-receipt.json` records all source and toolkit Python hashes, runtime versions and mapped mesher/OpenSSL binary hashes. The surface has 25,195 vertices and 50,478 triangles; the mesh has 43,880 nodes and 193,760 tetrahedra. The reproduced PNG matches the record's `exports/leg/fea/hip_frame-E1.png` (SHA-256 `8725874f3b193d8cc9738fb331f70f64a8e5fd0c023a11d7ecbee0233794da4e`).

Run CAD only on the isolated compute environment following the remote-run skill. Its manually installed mesher requires the matching crypto and SSL libraries in **process-local** `LD_PRELOAD` before Python starts; `hashlib` can load system OpenSSL before a later `import gmsh`. Do not change global linker settings or a shared environment. Paths and host mapping remain in private team configuration; the public receipt records binary identity, not private host details. The successful run and collect locations are tracked in [issue 69](https://github.com/Valpatel/gyropup/issues/69), and for the v0.6.0 regeneration in [issue 29](https://github.com/Valpatel/gyropup/issues/29).

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

The source/artifact checker verifies historical source blobs, current report identity, field dimensions/units and physical displacement, complete input/output hashes, bounded load timeline, codec, duration and all 288 decoded frames. It independently compares the model region in unloaded and loaded frames with the same camera direction, excluding captions. The shipped loop changes 30.72% of sampled color channels by more than 20 levels, with mean absolute difference 31.99/255. A frozen-frame negative control must fail; a 12-second container alone is insufficient. Twelve artifact/metadata mutations must also fail.

The browser harness exercises real decoded playback, pause, keyboard controls, reduced motion, muted autoplay, 320×568, 390×844, 844×390 and 1440×900 layouts, actual 3D field rendering, missing clips, HTTP503, invalid media, retry, case switching during a held request and stale result identity. Installed Google Chrome, pinned Playwright Chromium (the CI engine) and WebKit pass. The player chooses AVC High level 3.1 when supported and the VP9 companion otherwise; both encodings are fully decoded and compared against the same model-region samples. The mean inter-codec pixel difference is 0.83/255. Browser tests use an isolated pinned Playwright cache to avoid other worktrees garbage-collecting a required browser version. Markdown reuses the published player adapter and preserves the watch link and scientific limits.

Reports without published clips show their still image with an explicit explanation. Failed clips retain the report and still with a retry action. Neither state displays a zero-second player. These checks establish presentation and artifact integrity; they do not independently validate the mechanical model or qualify the part for manufacture.
