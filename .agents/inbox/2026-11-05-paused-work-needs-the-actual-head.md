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

## Keep draft limits separate from the published branch

On 2026-11-06 UTC (2026-11-05 local), the dossier relocation proposal incorrectly called the draft's +12/+10
limits released behavior. Source inspection caught the branch-attribution error before implementation:

```text
git show 2a2e4853012ae16179818fea22f8f4a69b57bae1:firmware/turret/config.py
  TILT_MAX_DEG = 0.0; TILT_MIN_DEG = -25.0
same main, cad/turret.py:2167 / designer/turret_bench.js:485
  tilt_range_deg [G.tilt_min, 0.0] / slider max 0
git show eeccc07bacfca95464c703f6d730f975781f1fe0:firmware/turret/config.py
  TILT_MAX_DEG = 12.0; TILT_MIN_DEG = -25.0; FIRE_TILT_MAX_DEG = 10.0
PR 207 remains open/draft/unmerged
```

The dossier's R3/R10 0/-25 wording therefore does not itself show staleness against published main. Other real
dossier problems remain: the main-source no-write reader probes returned 27 errors/two warnings and six stale
geometric gate rows before and after the proposed move. Reader/input equality does not establish that either
verdict is correct, current geometry is reconciled, or a physical angle is qualified.

The [dated correction](https://github.com/Valpatel/gyropup/issues/219#issuecomment-6679425030) and
[independent source check](https://github.com/Valpatel/gyropup/issues/219#issuecomment-6679458067) preserve that
distinction. No historical report, YAML value, mechanical or firmware limit changed. Cause: correctly recovered
draft facts were later transferred into a statement about a different branch. Corrective rule: write the exact
branch/head beside every numerical comparison and check both immutable sources before calling it released or
using it to diagnose stale evidence. A branch audit proves only its named branch; a matching reader result proves
only the tested contract. Retain actual errors and physical unknowns separately.
