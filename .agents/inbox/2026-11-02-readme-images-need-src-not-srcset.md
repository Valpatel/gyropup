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
