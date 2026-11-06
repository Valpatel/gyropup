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
