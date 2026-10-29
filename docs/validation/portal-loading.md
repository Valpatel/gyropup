# Portal loading behavior

Issue49 compares loading feedback with actual usable data. The changes reuse the existing pages and models; they do not change CAD datums, mass reports, physics recordings or robot controls.

| Page or operation | Expected behavior | Earlier behavior | Implemented contract |
| --- | --- | --- | --- |
| Build | A parts/print total exists only after its required catalog and plans are usable. | Catch-all fetch fallback treated network and parse failures like missing workstreams. | HTTP/format failures show retry without a total. Only optional404 is unpublished; incomplete workstreams are excluded and the remainder is labeled a published-data subtotal. |
| Progress | Each report explains its own loading, unavailable or failed state. | Sequential waits and swallowed errors could leave blank sections and hold unrelated reports. | Independent statuses and retries; late responses cannot overwrite newer data. A retry preserves unrelated report nodes. |
| Generic CAD viewer | All required parts must download, parse and render before ready. | Raw JSON/STL loads could fail without a recovery action. | Manifest, consumed kinematic dimensions/mounts, HTTP, STL payload and finite/nonempty geometry checks precede scene readiness. Retry uses the same utility route and controls appear once. |
| Structural viewer | Download and decode phases remain visible until a usable first frame. | A static wait did not explain failures or offer retry. | Report payload and surface arrays are validated before replacing the report index. Missing/malformed surfaces get a readable explanation and retry. |
| Character demo | Required model failures should be recoverable without recreating a working conversation. | An uncaught model failure left an ambiguous static page. | Startup status persists through model preparation; retry retains the stage canvas. Conversation/event controls are mounted only after the model succeeds. |
| Service detection | The user can tell that detection is pending, and cannot start overlapping requests with the button. | The button stayed active with stale “not checked” text. | Pending status, disabled button, explicit failure/retry and preserved Talk instance. |
| Landing preview | Show honest startup feedback while retaining the matching poster. | The poster remained useful but visitors could not distinguish loading from failure. | Import-independent status, explicit error and keyboard/native retry before readiness; a stale retry cannot reload a usable hero. |
| Optional navigation | A slow navigation index cannot hold app startup. | Several routes awaited the optional index before rendering. | Bounded, nonblocking navigation with local links; each route continues its own data load. |
| Entry JavaScript | A held module remains loading; an actual import failure offers recovery. | A failed entry graph could leave static Loading text forever. | Static CSS/status plus guarded dynamic import; native Reload page is offered only before a usable scene exists. Later data retries keep their state. |
| Simulator model/recording changes | Pending work is visible while existing play and conversation survive. | Error hints could disappear into the collapsed talk dock. | Token-guarded status with retry/cancel and native controls. New live input cancels stale recording selection. |
| Required bench geometry | A failed required mesh cannot become a ready partial turret. | Individual failed parts were caught and skipped. | The complete 66-part bench is required; failure retains the prior scene and conversation. |
| Recording and summary data | Validate data before changing the live scene or presenting readouts. | Malformed cached metadata could make retry ineffective; invalid recording contents could reach scene mutation. | Retry refetches invalid metadata. Finite consistent frames, joint/prop/mover indices and event structure are checked before presentation changes. |
| Agent Markdown | Static content comes from validated published data. | The old adapter understood only the nav import and would reject the new portal imports. | The adapter evaluates the same published pure data reader, adapts UI status only, and rejects any failed required section. No checkout-data fallback. |

## Verification

`tools/test-loading-portal.mjs` is a built-site browser test. It intercepts individual data and entry-module requests rather than slowing the entire browser. Five route cases hold and fail the entry graph, including the shared loading helper, then use the native reload control. The current 24 cases include held downloads, HTTP503, offline request failure, malformed JSON, optional404, stale success and failure after a retry, HTML/empty STL, a misleading ASCII prefix that would select the binary parser, malformed FEA surfaces, and retry on the existing character canvas. It checks actual renderer calls before ready, no duplicate controls, independent report-node identity, keyboard-focused 44px retry targets, 320px portrait and 568px landscape visibility, reduced-motion behavior, and escaped page exceptions.

Run against a coherent built preview:

```sh
SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
npm run test:markdown
```

The harness writes a report containing the fetched site version, case names and errors, plus screenshots, under `TEST_OUTPUT` (default `/tmp/gyropup-loading-portal`). On 2026-10-29 UTC, the final 24 cases passed Chromium and WebKit on revision `dd7071022f2ea609ae7d420932064d7003fa3acc`, assets `28809d372e4d593b7cbe`, built `04:51:59.892Z`. Start/end version equality rejects a mixed-build run. Receipts are `/tmp/gyropup-pr51-portal-final/{chromium,webkit}-report.json`; both report no escaped page exceptions. Phone screenshots show readable reload/retry controls, including the explicit CAD route's long title after the mobile grid correction.

The eight malformed robot-manifest variants were rejected before any STL request or conversation mount. Native retry of the valid manifest kept the canvas, mounted one conversation dock and produced zero non-finite world matrices. Required archive HTTP/mesh failures remain distinct from the explicit unavailable/mismatched-design fallback.

`node --test tools/test-portal-data.mjs` passed two focused tests using actual HTTP header/body stalls and STL-classifier negatives. `npm run test:markdown` passed five tests after integrating the prototype notice, including rejected malformed published reports and no local-data fallback. The existing viewer suite passed Chromium and WebKit after the data-recovery changes, including 21 FEA sizes and five Talk layouts; those runs preceded the final safety-header integration, whose focused narrow-route regression is included above.

The actual current-model suite also passed Chromium on the same frozen final build: 48 parts across 46 independent required poses and 90 operating frames, maximum landmark error 0.000010 mm, five negative controls, preserved archive/current frames and identical hero/sim/Talk geometry. The standalone motion-trace validator passed all 136 samples and 46 required poses. Receipts, delivered-source hashes, full trace and visible shot-at-mouth screenshot are in `/tmp/gyropup-pr51-models`. This verifies rendering/motion references, not new physical dynamics or hardware safety.

`tools/test-loading-sim.mjs` separately exercises native retry after a real request timeout, malformed summaries/recordings, HTTP503 and invalid required bench STLs; it checks preserved scene/conversation identity and visible feedback above phone overlays. `tools/test-loading-hero.mjs` covers three delayed layouts, failed entry/dependency/STL/WebGL, repeated failure, keyboard recovery, stale retry, reduced motion and no-script behavior. Their final current-head/hosted receipts belong on the PR alongside the existing model, viewer, mechanism, gameplay and audio regressions. Local passing receipts do not establish deployment.

## Limits

The tests exercise specific network/format failures in two browser engines, not every physical phone or real network. The loading helper provides operation labels, not byte progress or invented percentages. Geometry validation establishes that required renderable data exists, not physical manufacturing validity or the correctness of FEA conclusions. Retries for first-load failure preserve the character canvas; this does not claim automatic restoration after a lost WebGL context. Deployment remains a separate check against its actual version.
