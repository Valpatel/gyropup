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

## Historical capture fixtures can require a narrower caller fix

The ba89804 correction passed the actual CI Chromium/WebKit15-group guide suites,
then the existing highlight-media source guard failed because its immutable
capture closure includes `tests/site/content/test-prototype-session.mjs`.
The layout/presentation aggregate failures only propagated that failure.
[The retained actual job/artifact](../plans/assembly-staging/ci-build-local-origin/ba-failure.json)
binds the50-member archive and preceding reports. No media or guard was stale
merely because a general test helper looked like a convenient place for the fix.

Corrective rule: inspect recorded-source consumers before modifying a shared test
fixture. Preserve a historically bound helper exactly when the new requirement is
local to another suite. The Build guide now owns the same tiny guarded init
function in its test directory; it leaves the historical helper at recorded
SHA997a3929. Its4tests and strict error observer remain, and the unchanged actual
highlight-media binding/decode/fault command passes. This refines the earlier
shared-helper recommendation above: reuse is subject to actual ownership and
recorded capture contracts, rather than a reason to re-seal unrelated media.

The new8-outcome browser control and ordinary23tests pass; the product/runtime,
old source receipts, timeouts and error handling are unchanged. Details and limits
are in [the separate correction checkpoint](../plans/assembly-staging/ci-build-local-origin/README.md).
Local Chrome remains different from CI's pinned Chromium, and this source fix
still needs new final-head review/CI. Neither the original073 nor ba run is
retroactively passing.
