# Resume paused work from its actual tree and reports

On 2026-11-05, the paused #201 / PR #207 description still said #196 had not
landed, the upper stop remained at zero, and no elevated-feed pose double-fed.
The immutable branch at `eeccc07bacfca95464c703f6d730f975781f1fe0` instead
included #196, the moved stop, later feed/FEA exports and four evidence failures.
The old prose would have caused repeated implementation and hidden known limits.

Dated commands and observations:

```text
git log eeccc07bacfca95464c703f6d730f975781f1fe0
  53787b1b merges dev after #196 / b408b59b
  later commits move stop and refresh feed, selected FEA and geometry studies

git show eeccc07bacfca95464c703f6d730f975781f1fe0:exports/turret/limits.json
  tilt min=-25, max=12; fire_tilt_max_deg=10

same head, feed/feed-elevated.json
  54 feeding + 18 parked cases; double_feeds=15; parked_leaks=0
same head, fea/summary.json
  28 rows; 9 below target; all_ok=false
  everyday minimum 1.50 (baseline 1.53); rare minimum 0.98
  latest refresh identifies only tilt_yoke, stop_lug and cradle

gh pr checks 207 --repo Valpatel/gyropup
  four failures: retained-fit-job, mechanism, loading, build-portal
```

Independent review also found a remaining above-level docstring in
`firmware/turret/host.py:24`, even though its actual aim path at line 518 uses
`C.TILT_MAX_DEG`. Thus a broad “all old phrases removed” claim would also have
been wrong. The corrected description and checklist qualify audited consumers
and retain that prose cleanup, partial refresh and nine failing strength rows.

Cause: the branch advanced through dependency integration and regenerated
artifacts while its PR body and issue checklist retained an earlier phase.
Neither a checked box nor an old paused lease describes the actual source.

Corrective rule: pin the current server head, inspect its ancestry and actual
code, then read the reports' verdicts, cases, inputs and refresh scope before
editing a recovery checklist. Separate implementation presence, historical
execution, passing acceptance and physical qualification. Compare the source
head again before publishing. Review documentary corrections independently,
read them back, and claim only their scope; leave implementation ownership and
original branches/receipts intact. A metadata correction needs no fake CAD run
or mirror test, but subsequent implementation still needs genuine provenance
repair, exact-source checks and independent review.

The [public audit](https://github.com/Valpatel/gyropup/pull/207#issuecomment-6675731285)
records the reviewed body/checklist identities and reciprocal issue checkpoint.
Only GitHub descriptions changed; #201 remains open and #207 draft at the same
head. No source, decision, receipt, hardware or physical acceptance changed.
D77's recorded owner decisions are preserved and attributed, without claiming
this documentary audit independently verifies their original statements or
physical behavior. Rangefinder integration remains separate proposed work.
