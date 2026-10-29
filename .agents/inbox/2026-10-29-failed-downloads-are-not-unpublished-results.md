# A failed download is not an unpublished result

On 2026-10-29 UTC, the loading-state audit for issue49 found portal helpers turning every fetch or parse failure into `null`. Build could therefore treat a failed parts list as missing work and display a plausible subtotal; Progress could silently leave a section blank. The viewers waited on raw fetch/JSON/STL decoding with no usable retry state.

Receipt from the focused built-site harness on the issue49 branch:

```sh
SITE_URL=http://127.0.0.1:8892 node tools/test-loading-portal.mjs
PASS held Build data and optional navigation
PASS Build http recovery
PASS Build parse recovery
PASS Build offline recovery
PASS Explicit optional404 remains unpublished
PASS Progress independence and stale success
PASS Progress independence and stale failure
PASS Independent report failure versus optional404
```

Those eight case results were observed on 2026-10-29 at04:22UTC; they are a partial test receipt, not a claim that the entire browser suite or deployment passed. The complete run and version belong in the harness JSON artifact and PR.

The old guard answered whether any data object existed, not why it was absent. Catch-all fallback erased the distinction between an optional unpublished artifact, an interrupted transfer and an invalid required response. A spinner alone would not repair that classification.

Rule: only an explicitly optional HTTP404 becomes unavailable. Required HTTP/parse/geometry failures remain visible and retryable; totals and models cannot become ready from those failures. Independent reports need independent status; request-generation guards protect both feedback and data mutations. The durable contract and regression entry points are in [loading readiness](../domains/loading-readiness.md).

Limits: this validates availability and rendering readiness, not the physical accuracy of CAD/FEA reports. A local passing browser run does not prove hosted deployment or a real device/network combination.
