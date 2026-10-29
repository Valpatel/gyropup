# Hosted navigation must accept the canonical route

On 2026-10-29 the independent hosted viewer-theme check reached the correct Build page after the native Back to parts click, but its exact `/designer/build.html` wait timed out. Cloudflare returns HTTP308 to the canonical `/designer/build`; the local static server preserves `.html`. This was a harness portability defect, not failed navigation.

`tools/test-file-viewer-theme.mjs` now accepts only the same origin and the exact `/designer/build` or `/designer/build.html` path, without query or fragment. It preserves the native click and the strict original href/download assertions. The final corrected hosted suite is rechecked by the independent release reviewer; it is not waived or replaced with direct navigation.

Corrective rule: validate a destination's exact canonical route family across local and hosted servers. A legitimate redirect does not permit a different origin or arbitrary path. Keep the click that exercises product navigation, and retain the served version receipt with the browser result.

Limits: this correction concerns one known Cloudflare route normalization. It does not weaken module, asset, missing-resource or external-request checks and makes no app change.
