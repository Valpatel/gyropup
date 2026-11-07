# README images must use `src`: the site build does not rewrite `srcset`

On 2026-11-02 the README gained an animated banner. GitHub's documented way to show a different image per theme is a
`<picture>` with `<source media="(prefers-color-scheme: dark)" srcset="...">`. `tools/build-site.mjs` publishes
README.md as `/site/pages/readme-md.html` and rewrites repository-relative `href` and `src` attributes to site paths,
but not `srcset`. A relative `srcset` would resolve under `/site/pages/` and 404, and a `<picture>` whose matching
source fails shows a broken image instead of falling back to its `<img>`.

## Corrective rule

Give README images one `src`. For a light and dark banner, use one SVG that switches its own colours with a
`@media (prefers-color-scheme: dark)` rule and paints its own background, so a mismatch between the page's theme and
the browser's stays readable. `docs/img/hero/gyropup.svg` works this way.

## Check

`npm run build`, then confirm `dist/site/pages/readme-md.html` has `src="/docs/img/hero/gyropup.svg?v=..."` and
that `dist/docs/img/hero/gyropup.svg` exists (the file must be tracked before the allowlisted build copies it).

## Keep navigation graphics proportional in the rendered page

On 2026-11-06 the owner reported that the “One robot. Four ways in.” graphic overwhelmed the repository entrance.
Its SVG had only a portrait `viewBox="0 0 420 636"`; the actual published-page CSS expanded it to about
1044 × 1581 px at a 1440 px viewport. Chromium and WebKit both reproduced that size using the original SVG
from `ad940ade` and the original unconstrained image attributes in the built README consumer. Passing overflow
checks did not establish a useful proportion.

The replacement uses a compact 640 × 224 SVG and explicit image dimensions in both Markdown consumers. An
initial phone preview also exposed the page's inherited 8 px image padding; removing that padding on these two
images preserved the intended aspect ratio. The actual built pages at `1f173211` measured 640 × 224 px on desktop
and about 354 × 124 px at a 390 px viewport. Both engines and themes passed; the original image still fails that
compact-size check. The four ordinary README links share the image's paragraph so the document renderer keeps
them visible instead of folding them into the following prose. The SVG retains reduced-motion behavior and
four links when opened directly; GitHub's image embedding does not make those inner links independently usable.

Check the actual built HTML (`npm run build`), not only the SVG source: inspect its displayed dimensions,
inherited padding, phone and desktop views, light/dark palettes, reduced motion and visible ordinary links.
`npm run test:markdown` checks generated routes, but cannot judge visual proportion. A compact navigation map
has a different purpose from a detailed engineering drawing; do not impose this image's dimensions on every figure.

Independent review then caught a different consumer: opening the compact SVG directly on a phone still gave
its root a fixed 640 px viewport, leaving two destinations off screen in both engines. The embedded image
checks and four-link count had passed. Make the SVG root itself responsive as well as its embedding, and check
the direct document's scroll width and all four link rectangles. Keep the actual fixed-width source as a failing
control; link presence and animation state alone cannot establish usable navigation.

## External SVG motion needs an explicit still and tested single-URL rewriting

The 2026-11-07 README refinement adds a bounded exception to the original `src`-only rule:
`picture/source` may select one generated still SVG through a single-URL `srcset`.
The compiler must resolve that source-relative URL and the cache pass must version
it just as they do the fallback `img/src`. Multi-candidate lists, descriptors,
whitespace and comma-separated paths are deliberately unsupported and rejected;
this is not a general responsive-image parser. The ordinary `img/src` fallback,
explicit compact dimensions and visible ordinary navigation remain mandatory.

A parent page's reduced-motion emulation alone did not reliably stop external SVG
image animations in the two observed browser engines. Generate the explicit still
with final `animation:none!important`, select it using parent-picture media, and
check the actual image's `currentSrc`, successful decode, aspect and pixels over
elapsed time. The source-SVG prototype in Chrome151 and WebKit26 passed phone and
desktop/light/dark normal-versus-reduced cases; an intentionally animated wrong
still changed pixels and was rejected in both engines. That prototype is not a
compiled-site result: the existing document-page tests apply the same acceptance
and negative control to the actual build. Standalone SVG media checks and font or
intrinsic-width observations do not substitute for this image-mode behavior.

## A picture wrapper must have the visible image's real box

On2026-11-07 UTC, PR246 at16271b3b passed its twelve document tests but failed
its full153-page wall sweep: Docs README measured1282px without a qualifying
visual, exceeding the unchanged1200px limit (five existing backlog entries).
The actual image was visible640×240, but its default inline `picture` box was
only640×19. The established nested-visual de-duplication measured the outer
picture and correctly rejected that tiny box; the child image was then excluded.

An actual `loadWallPage`/unchanged `longestStretch` probe on the exact compiled
product reproduced it. A bounded block picture plus block image, with the now
redundant following BR removed, made both boxes640×240: Docs749px and root487px
instead of1282px and723px. Fix the real wrapper geometry, not the1200px threshold,
backlog or measurement exclusions. The existing two-README browser test now
requires wrapper/image x/y/width/height to agree. This source correction still
needs its own normal current CI and compiled two-engine readback after the
account-switch pause; the temporary live-DOM probe is not final publication.
