# Bind prior evidence before combining coverage counts

On 2026-11-10, independent PR280 review of frozen d8442c61 replaced every query
ID in the supplied 42-row prior264 report with an unrelated hash. The portable
265 audit checked only 42 unique IDs disjoint from the two current controls. It
still exited0 and wrote the identical accepted 44/90 receipt. The genuine native
artifacts remain valid; this was a checker false acceptance, not a new CAD result.
The [review finding](https://github.com/Valpatel/gyropup/pull/280#discussion_r4528726930)
and [exact counterexample](../plans/assembly-staging/native-265/review-counterexample/README.md)
are retained with the correction. Dated command/output evidence:

```text
2026-11-10: old independent-audit.py <fetched265> <263-manifest> <full-plan> <42-fake-ID-prior> <fresh-receipt>
exit=0; wrong_prior_all42ids_replaced=true; same_summary_bytes=true
2026-11-10: python3 -B -m unittest discover -s tests/site/assembly -p test_robot_native_audit.py
3 tests + 8 mutation subtests PASS; actual corrupt-input CLI nonzero; no receipt
2026-11-10: corrected independent-audit.py <fetched265> <263-manifest> <full-plan> <sealed264-report> <fresh-receipt>
exit=0; receipt byte-identical to original accepted265 receipt
```

Cause: a count and set-disjointness check did not bind supplied prior evidence to
its retained run or the plan. Corrective rule: verify the required prior byte
seal and independently required ordered query membership before deriving combined
coverage. Here the report is exactly17899bytes, SHA0cfa0ef2f07ed9278855ac1579d911a246a01d9e134d7bad3b69f7d74c99d49d,
with the first42 IDs of the sealed90-query plan,36clear/6seat states, expected
fixed instance/travel and consistent transient/terminal flags. Reject altered
bytes and semantic changes before emitting a successful receipt. The helper is
import-safe and tested in ordinary CI; the CLI regression needs no native archive.

This extends the existing [complete-evidence lesson](2026-10-29-receipt-coverage-must-not-be-optional.md):
counts require independently stated membership and actual byte identity. Limits:
these guards bind recorded evidence, not physical truth. They introduce no CAD
query, overlap exemption, manufacturing approval or additional completed path.
The existing44 completed/46 uncompleted scope remains unchanged.
