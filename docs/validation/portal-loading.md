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
| Optional navigation | A slow navigation index cannot hold app startup. | Several routes awaited the optional index before rendering. | Bounded, nonblocking navigation with local links; each route continues its own data load. |
| Entry JavaScript | A held module remains loading; an actual import failure offers recovery. | A failed entry graph could leave static Loading text forever. | Static CSS/status plus guarded dynamic import; native Reload page is offered only before a usable scene exists. Later data retries keep their state. |
| Simulator model/recording changes | Pending work is visible while existing play and conversation survive. | Error hints could disappear into the collapsed talk dock. | Token-guarded status with retry/cancel and native controls. New live input cancels stale recording selection. |
| Required bench geometry | A failed required mesh cannot become a ready partial turret. | Individual failed parts were caught and skipped. | The complete 66-part bench is required; failure retains the prior scene and conversation. |
| Recording and summary data | Validate data before changing the live scene or presenting readouts. | Malformed cached metadata could make retry ineffective; invalid recording contents could reach scene mutation. | Retry refetches invalid metadata. Finite consistent frames, joint/prop/mover indices and event structure are checked before presentation changes. |
| Agent Markdown | Static content comes from validated published data. | The old adapter understood only the nav import and would reject the new portal imports. | The adapter evaluates the same published pure data reader, adapts UI status only, and rejects any failed required section. No checkout-data fallback. |

## Verification

`tools/test-loading-portal.mjs` is a built-site browser test. It intercepts individual data and entry-module requests rather than slowing the entire browser. Five route cases hold and fail the entry graph, including the shared loading helper, then use the native reload control. The current 22 cases include held downloads, HTTP503, offline request failure, malformed JSON, optional404, stale success and failure after a retry, HTML/empty STL, a misleading ASCII prefix that would select the binary parser, malformed FEA surfaces, and retry on the existing character canvas. It checks actual renderer calls before ready, no duplicate controls, independent report-node identity, keyboard-focused 44px retry targets, 320px portrait and 568px landscape visibility, reduced-motion behavior, and escaped page exceptions.

Run against a coherent built preview:

```sh
SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
npm run test:markdown
```

The harness writes a report containing the fetched site version, case names and errors, plus screenshots, under `TEST_OUTPUT` (default `/tmp/gyropup-loading-portal`). The first Chromium and WebKit runs on 2026-10-29 passed 16 cases each on assets `05b7af7b56c9dc30dbd8`, built 04:21:21.082Z. That build included then-uncommitted simulator fixes, so revision 78514d9 alone does not identify its source. Screenshot review then found the malformed-surface error leaking an internal `b64` exception; the follow-up replaces it with a readable data error and adds a negative text assertion. The follow-up passed both engines on assets `a15e698567e6c065d293`, built 04:25:47.224Z. Entry-module fallback was added afterward. The final 21-case suite passed Chromium and WebKit on assets `9bb0039d1729514609aa`, built 04:32:45.121Z; screenshots confirmed readable native reload/retry controls. The same build passed the focused simulator suite in both engines: startup/model/mesh each required two attempts, malformed summary required three, and four malformed recordings were rejected before the fifth valid response. Those source edits were subsequently committed as `3c67ad3` and `886a1b4`; the build revision metadata predates them. Production verification remains separate.

`npm run test:markdown` passed 4 tests on 2026-10-29, including rejected malformed published reports and no local data fallback. The existing viewer suite also passed Chromium and WebKit after the data-recovery changes, including 21 FEA sizes and five Talk layouts. `tools/test-loading-sim.mjs` separately covers held/failing startup, metadata, models, bench parts and recordings; it checks native retry/cancel, preserved scene/conversation identity and visible error text above phone overlays. Existing `test:viewers`, `test:models` and audio/control suites remain regressions for layout, mechanisms and conversation behavior; this test does not replace them.

## Limits

The tests exercise specific network/format failures in two browser engines, not every physical phone or real network. The loading helper provides operation labels, not byte progress or invented percentages. Geometry validation establishes that required renderable data exists, not physical manufacturing validity or the correctness of FEA conclusions. Retries for first-load failure preserve the character canvas; this does not claim automatic restoration after a lost WebGL context. Deployment remains a separate check against its actual version.
