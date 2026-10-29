# Hosted navigation must accept the canonical route

On 2026-10-29 the independent hosted viewer-theme check reached the correct Build page after the native Back to parts click, but its exact `/designer/build.html` wait timed out. Cloudflare returns HTTP308 to the canonical `/designer/build`; the local static server preserves `.html`. This was a harness portability defect, not failed navigation.

`tools/test-file-viewer-theme.mjs` now accepts only the same origin and the exact `/designer/build` or `/designer/build.html` path, without query or fragment. It preserves the native click and the strict original href/download assertions. The final corrected hosted suite is rechecked by the independent release reviewer; it is not waived or replaced with direct navigation.

Corrective rule: validate a destination's exact canonical route family across local and hosted servers. A legitimate redirect does not permit a different origin or arbitrary path. Keep the click that exercises product navigation, and retain the served version receipt with the browser result.

Limits: this correction concerns one known Cloudflare route normalization. It does not weaken module, asset, missing-resource or external-request checks and makes no app change.

The corrected hosted run reached the final external-request assertion and exposed a second hosting assumption: 25 requests for the same injected Cloudflare Insights beacon, with all 21 viewer layouts and page-error/missing-resource checks passing. The harness now records that exact observed HTTPS script pathname separately, only when testing Gyropup's HTTPS production or project Pages host. Different hosts, paths, query strings, methods or resource types still count as unexpected externals and fail. The complete hosted suite is rerun after this classification; no Cloudflare settings or product dependencies change.

## Static preview links and outgoing metadata requests need separate evidence

On 2026-10-29, main `874f961b82551fcecfa2655c9edbf452c88bf8a9` passed the live Progress and Build suites in Chrome and WebKit. The carrier check reached `/site/pages/docs-carrier-service-connectors-md` through Back to parts, then timed out waiting for `?live=0`. Both receipts had no page errors or HTTP failures. The static build creates a usable preview link before `web/model-links.js` finishes loading the inventory; its return address has no artificial local-preview query. The enhanced link includes the current query. Requiring the enhanced form for both was a harness defect.

`tools/test-carrier-inspection.mjs` now explicitly exercises the static fallback at 320px and real enhancement at 390px and 1440px. It checks the advertised document, the viewer's unchanged Back href, and native return to that exact canonical route with the advertised query. It does not replace the click with a direct navigation. `tools/test-hosted-navigation.mjs` rejects wrong origins, wrong documents, unexpected queries, and dropped enhanced query data.

The failed live receipts also contained canceled `/site/models.json`, `/site/nav.json`, and Cloudflare `/cdn-cgi/rum?` requests during navigation. `tools/hosted-navigation.mjs` snapshots pending request identities before each explicit outgoing navigation. Only those already pending, exact same-origin metadata GET/fetch requests with observed cancellation errors are recorded separately; new-page failures, model/module failures, non-cancellation errors, and HTTP failures remain fatal. Exact HTTPS Gyropup hosting POST/ping or POST/fetch telemetry cancellations are recorded separately. They are not dependencies of the viewer. Tests reject unrelated URLs, methods, request types and errors.

Reproduce: `SITE_URL=https://gyropup.com npm run test:carrier-inspection`; repeat with `PLAYWRIGHT_BROWSER=webkit` and the installed browser cache. Reports include the served version, original STEP hash, both advertised/actual return addresses, all cancellations, and actual model/control observations. This test-only correction does not change site assets, geometry, readiness, or Cloudflare configuration. Issue #99 carries the final execution and independent review receipts.
