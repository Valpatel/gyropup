# Seed browser fixture storage only on its intended HTTP origin

PR289 source073693f CI's build-portal Chromium test correctly exposed its own
initialization fixture:9 `sessionStorage` access-denied page errors were recorded,
all on `about:blank`, across core/switching/fallback/touch phases. Unsupported
live-poller requests were zero. The [actual failed artifact](../plans/assembly-staging/ci-origin-fixture/original.json)
retains its zip/report hashes,10members/CRC pass and opaque document ownership.
This was neither a product notice failure nor browser noise to filter.

The context-wide error observer catches errors from initial/child documents as
well as visible application pages. The helper previously wrote storage without
checking the document's origin. Corrective rule: reuse the existing acknowledged
session helper, bind its intended site origin, and return before any storage
access on non-HTTP(S), opaque or wrong-origin documents. Use the serialized
security origin (`globalThis.origin`) so opaque sandboxed HTTP documents also
fail closed. Existing callers default to SITE_URL when set and keep HTTP-only
standalone compatibility when unset. Matching-origin storage errors remain
observable; no catch or error-array exemption is added.

2026-11-10 actual nativeChrome151/existingWebKit controls used the real shared
helper: oldopaque writes raised2/1 errors; guarded opaque/wrong-origin writes
were absent, and the real `/site/` page remained acknowledged. An intentionally
denied matching HTTP store and an ordinary HTTP script exception each still
reached the page-error observer. The [qualified control receipt](../plans/assembly-staging/ci-origin-fixture/actual-controls.json)
preserves all8 outcomes.4 ordinary VM tests execute the actual transported init
function, including denied storage accessors and matching-origin propagation.

Limits: local nativeChrome differs from CI's pinned bundled Chromium. Affected
suite/final-head CI remains required. Only test fixture code changes; the product
notice, storage-failure behavior, strict error capture and page timeouts remain.
