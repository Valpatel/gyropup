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


## A fresh media capture must guard every context init before storage access

On 2026-11-11 UTC, planning the archive-retry correction's required media refresh
traced the accepted76cc envfix capture's22 retained initial-document errors:
14from seven hero-parity contexts and8from four recorder contexts. Each context
ran both unguarded local preferences and the old shared session acknowledgement.
The [canonical adoption receipt](../plans/end-packs-highlights/adoption.json)
preserves original messages/stacks, all9successful child commands and the actual
exit1 `COMPLETE_CANDIDATES_WITH_OPAQUE_DIAGNOSTICS_REVIEW_REQUIRED` outcome.
That qualified artifact review did not make the initialization fixtures correct.

The new caller correction reuses the existing Build suite's HTTP-origin-aware
acknowledgement. Hero preferences and recorder seeding check protocol, serialized
security origin and the explicitly intended origin before touching storage,
random state or live-mode hooks. On the intended HTTP origin, the same preference
keys, deterministic random sequence and live hook remain. A denied matching store
still throws. The old shared helper and all historical media receipts stay byte
identical. The recorder and strict checker replace the now-unused old helper in
their exact three-member location inventory with the actual guarded helper;
missing/old inventories remain rejected. Changed renderer/recorder/checker inputs
require new frames and encoding, not altered hashes on the old capture.

The existing Node hero-output tests execute only the two named transported init
functions and the reused acknowledgement callback against synthetic origins.
They cover matching writes, deterministic seeding, no access on about:blank,
opaque HTTP and wrong-origin documents, and matching-store failure propagation.
The Python binding suite checks the exact new helper inventory and rejects the
old identity substituted into a self-consistent synthetic capture. These pure
controls establish fixture behavior, not a new rendered-media acceptance.

During control preparation, an incorrect five-call-site expectation failed;
the actual four call sites generate seven contexts through existing loops.
Node VM also converts a throwing global getter into `ReferenceError`; controls
therefore separately verify attempted accessor/failure escape and exact-error
propagation from a throwing storage method. Neither diagnostic changes browser
error handling or permits errors to be filtered.

A first planning inference incorrectly claimed that the private observer missed
`browser.newPage`. Inspection of the actual Playwright1.56.1 implementation
(`playwright-core/lib/client/browser.js`, `newPage`) shows it calls the observed
`this.newContext`; the retained producer audit confirms one poster context,
243response matches and zero recorded poster page errors. Public API names alone
do not establish an instrumentation gap. Any explicit direct-page wrapper is a
defensive observation change requiring deduplication controls and separate action
review, not a correction to a demonstrated missing prior page. No new capture,
runtime, zero-error or publication claim follows from this fixture correction.
Preserve the original failed dependency attempt, qualified22-error candidate
result and already-verified d694 public release.


## Compile the actual extractor and keep byte collection separate from worker success

The first authorized archive-retry media refresh on 2026-11-11 stopped before any
capture: private init-control.mjs:13 constructed an under-escaped regex and raised
`SyntaxError: Invalid regular expression … Unterminated group`. A syntax-only
`node --check` had not executed that constructor. The worker exited 1 and closed
its browser/listener. The collector then exposed a second assumption: it required
RUN-DONE to be the last line, while the unchanged worker prints its original
exception afterward. Both failures remain preserved in the
[actual failure checkpoint](https://github.com/Valpatel/gyropup/issues/306#issuecomment-6784963025).

The separately reviewed corrected packet reused the existing tested extraction
literal. Pure preflight invoked the actual old extractor (required rejection),
extracted and compiled both actual callbacks, and rejected a missing callback
before browser imports/launch. The terminal-log audit requires one exact DONE
marker matching the service exit and an exact original-error tail. Eight planted
log faults were rejected. Verified byte collection retains worker status/exit
separately; the collector propagates failed/incomplete exits 1/2 after saving its
byte receipt. A verified failed archive cannot become a successful worker.

The corrected run completed all 12 phases, 480 new frames and both 22-second movies with
zero production page errors. Independent review accepted the exact seven candidate
files. The [source-bound adoption receipt](../plans/end-packs-highlights/archive-retry-refresh.json)
records original failure, corrected action, raw/hash checks, source/native/runtime
pins, unchanged history and cleanup. Native Chrome capture and pure controls do
not establish final composed CI, WebKit/publication, performance or physical
qualification. No retry, parser exception or error filter rewrites the old outcomes.
