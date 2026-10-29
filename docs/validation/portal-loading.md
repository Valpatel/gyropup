# Portal loading behavior

Issue49 compares loading feedback with actual usable data. The changes reuse the existing pages and models; they do not change CAD datums, mass reports, physics recordings or robot controls.

| Page or operation | Expected behavior | Earlier behavior | Implemented contract |
| --- | --- | --- | --- |
| Build | A parts/print total exists only after its required catalog and plans are usable. | Catch-all fetch fallback treated network and parse failures like missing workstreams. | HTTP/format failures show retry without a total. Only optional404 is unpublished; incomplete workstreams are excluded and the remainder is labeled a published-data subtotal. |
| Progress | Each report explains its own loading, unavailable or failed state. | Sequential waits and swallowed errors could leave blank sections and hold unrelated reports. | Independent statuses and retries; late responses cannot overwrite newer data. A retry preserves unrelated report nodes. |
| Generic CAD viewer | All required parts must download, parse and render before ready. | Raw JSON/STL loads could fail without a recovery action. | Manifest, HTTP, STL payload and finite/nonempty geometry checks precede scene creation. Retry uses the same utility route and controls appear once. |
| Structural viewer | Download and decode phases remain visible until a usable first frame. | A static wait did not explain failures or offer retry. | Report payload and surface arrays are validated before replacing the report index. Missing/malformed surfaces get a readable explanation and retry. |
| Character demo | Required model failures should be recoverable without recreating a working conversation. | An uncaught model failure left an ambiguous static page. | Startup status persists through model preparation; retry retains the stage canvas. Conversation/event controls are mounted only after the model succeeds. |
| Service detection | The user can tell that detection is pending, and cannot start overlapping requests with the button. | The button stayed active with stale “not checked” text. | Pending status, disabled button, explicit failure/retry and preserved Talk instance. |
| Agent Markdown | Static content comes from validated published data. | The old adapter understood only the nav import and would reject the new portal imports. | The adapter evaluates the same published pure data reader, adapts UI status only, and rejects any failed required section. No checkout-data fallback. |

## Verification

`tools/test-loading-portal.mjs` is a built-site browser test. It intercepts individual data requests rather than slowing the entire browser. The current16 cases include held downloads, HTTP503, offline request failure, malformed JSON, optional404, stale success and failure after a retry, HTML/empty STL, malformed FEA surfaces, and retry on the existing character canvas. It checks actual renderer calls before ready, no duplicate controls, independent report-node identity, keyboard-focused44px retry targets,320px portrait and568px landscape visibility, reduced-motion behavior, and escaped page exceptions.

Run against a coherent built preview:

```sh
SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
npm run test:markdown
```

The harness writes a report containing the fetched site version, case names and errors, plus screenshots, under `TEST_OUTPUT` (default `/tmp/gyropup-loading-portal`). The first Chromium and WebKit runs on2026-10-29 passed16 cases each on assets`05b7af7b56c9dc30dbd8`, built04:21:21.082Z. That build included then-uncommitted simulator fixes, so revision78514d9 alone does not identify its source. Screenshot review then found the malformed-surface error leaking an internal `b64` exception; the follow-up replaces it with a readable data error and adds a negative text assertion. Final follow-up and deployed receipts belong on the PR.

`npm run test:markdown` passed4 tests on2026-10-29, including rejected malformed published reports and no local data fallback. Existing `test:viewers`, `test:models` and audio/control suites remain regressions for layout, mechanisms and conversation behavior; this test does not replace them.

## Limits

The tests exercise specific network/format failures in two browser engines, not every physical phone or real network. The loading helper provides operation labels, not byte progress or invented percentages. Geometry validation establishes that required renderable data exists, not physical manufacturing validity or the correctness of FEA conclusions. Retries for first-load failure preserve the character canvas; this does not claim automatic restoration after a lost WebGL context. Deployment remains a separate check against its actual version.
