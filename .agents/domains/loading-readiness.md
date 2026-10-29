# Loading readiness and report availability

Browser loading is an operation state, not a page animation. Keep a visible status until the requested data has passed HTTP, format and geometry validation and the first usable frame or report exists. Use `designer/kit/loading.js`; pass the token returned by `begin()` to every asynchronous completion. Callers must also guard their own DOM/scene mutations against stale requests.

`designer/kit/portal-data.js` distinguishes an explicitly optional HTTP404 from transport errors, other HTTP status codes and malformed data. An unpublished optional export can be labeled unavailable. A failed required catalog, report or mesh cannot become an empty list, a zero total or a partial assembly labeled ready. Build excludes incomplete workstreams and labels the remainder a published-data subtotal. Progress uses independent section states so one report cannot block unrelated reports.

A required STL must have a plausible STL payload and finite, nonempty triangles before the assembly becomes ready. Do not create a partial scene while required parts are still loading. Retrying the character model keeps its stage canvas; do not remount conversation controls on an already mounted robot. Download/parse phases are labels, not invented percentages.

Agent Markdown uses the same portal renderer and data reader against the published bundle only. UI status is adapted for static rendering; an error state rejects a partial snapshot. Optional unpublished sections remain explicit. Never add a hidden checkout-data fallback to make the static build pass.

`tools/test-loading-portal.mjs` injects held requests, HTTP503, offline failures, HTML returned as JSON/STL, empty geometry, malformed structural surfaces and stale progress completions. It checks retry behavior, unrelated report identity, first rendered frames, phone controls and reduced motion. `tools/test-markdown.mjs` verifies static failure isolation and published-data provenance. Existing model and portal-viewer suites remain necessary: loading tests do not establish mechanism correctness, scientific validity or good camera framing.
