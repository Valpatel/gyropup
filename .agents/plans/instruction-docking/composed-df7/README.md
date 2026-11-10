# Combined instructions-dock validation

2026-11-10, runtime/source `df7fec062753be4b0170c4d22453a6d44bf18def`.
Normal composition includes accepted PR279 `02d7fb71`, then PR280 `e3401b0a`.
Native261–265, hardware, firmware and collection/native helper bytes remain
identical to accepted280; no CAD or native run was performed here.

Both real browser reports pass132 states with no page errors. They cover desktop
independent docks, native Chromium fullscreen / WebKit expanded fallback,
portrait restoration, actual coarse touch844×390 versus fine-pointer desktop,
original first-triangle canvas selection after Isolate, fixed action footers,
320px long-label UI stress, keyboard navigation and real touch actions, and
stopped/already-paused/actively-playing contextual controls. The native phase
traces show real down/up/click targets and resulting section/player states.
The explicit `[UI TEST]` label stresses wrapping only; actual part metadata stays
unchanged. Local Chrome151 differs from pinned CI; normal CI remains mandatory.

The original narrow WebKit Robot sequence is retained separately in
`original-native-webkit-*.json`. It is WebKit desktop only, regardless of the old
script's inherited console summary. It passes genuine active→Loop→Rotate with
the button fixed at y665/scroll202, native hits and a paused clock. Independent
source/runtime review: [PR286 review](https://github.com/Valpatel/gyropup/pull/286#pullrequestreview-5847589130).

Commands on the built combined source:

```sh
npm run test:instruction-docking
PLAYWRIGHT_BROWSER=webkit npm run test:instruction-docking
python3 -B -m unittest discover -s tests/site/assembly -p 'test_robot*.py'
node --test tests/site/assembly/test-guide-state.mjs tests/site/assembly/test-guide-fallback.mjs tests/site/assembly/test-poster-contract.mjs tests/site/assembly/test-print-selection.mjs tests/site/assembly/test-print-mount.mjs
```

The harness imports createSiteServer on an assigned ephemeral port and closes the
browser/listener in finally. Report preview addresses are replaced with an
explicit temporary-preview placeholder. Source/version identities are retained.
Historical103-state evidence remains in the parent folder with its original
receipt; `bounded-pane-actions` preserves119-state and559 guide/interactions
passes, and `playing-2949` preserves the subsequent actual failure. None is
relabeled as current source validation.

After these passes, the renderer captured all12 actual1280×900 preserved WebGL
canvases on this exact source, in native fullscreen with normal right-docked
instructions. The receipt is `../../versioned-build-guide-poster-capture-current.json`.
The fresh PNG hashes equal the previous fixed-footer pixels; this was a new real
capture, not a receipt restamp. The changed playback source is bound by the new
visual contract. Attaching invokes only the neutral exporter; its60-output
check and fresh poster contract pass. Original native evidence is untouched.
