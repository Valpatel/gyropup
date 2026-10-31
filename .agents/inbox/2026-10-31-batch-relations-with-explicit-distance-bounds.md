# Batch repeated relation queries and preserve the distinction between bounds and measurements

On 2026-10-31, the RS04 contact investigation's exact-query loop remained on its
first ring after approximately 16 minutes, as reported by the compute-run owner.
It had logged `Probing od118-id80-t2.032 against all 43 motor solids and authored
rotating parts`; the initial implementation wrote no checkpoint until that ring
finished. The preserved run remains diagnostic evidence, not a completed result.

Read-only inspection of cad-agent v0.4.2 (`2ad4269`) established the cause of
avoidable repeated work:

```sh
sed -n '700,748p' src/cadagent/gates/relations.py
sed -n '881,974p' src/cadagent/gates/relations.py
```

`relate()` measures both input volumes on every call. Public `relation_table()`
memoizes adaptive volume integration within a table and performs its existing AABB
broad phase before exact queries. No new collision engine or tolerance was needed.

The research producer now uses one table per ring with `only=[ring]`, explicitly
retrieves all 59 required relations, and keeps the original eight candidates and
default tolerances. It records exact toolkit bounds and posed shape identities.
Remote `apart` rows are lower-bound evidence (`exact: false`); all pairs whose
boxes are within 1 mm remain exact. Actual motor-plate contact must be exact and
positive. Tables' ordinary iteration/JSON export omit broad-phase rows, so they
cannot replace the explicit required-pair inventory.

The kernel-free guard independently recomputes AABB separation. It rejects
inexact rows at or below the 1 mm near margin, invented exact contact/volume fields,
changed boxes, missing members and promoted acceptance. It constrains ring boxes
to their known dimensions and binds counterpart boxes to reviewed inventories.
This matters because `RelationTable.get()` can label an excluded pair apart at
the smaller touch tolerance; the investigation's guard must enforce its actual
near-phase contract. Six-decimal distance serialization permits rounding error,
not a wider physical tolerance.

2026-10-31 local regression evidence:

```sh
python3 -B tools/test-rs04-support-probe.py --pure
# Ran 17 tests; OK (skipped=1: actual result awaits independent review/pinning).
```

Baseline and footprint checkpoints now precede the expensive candidate loop, and
each completed ring records timings and query counts. Failed checkpoint replacement
preserves the previous diagnostic. No speedup or new geometric clearance is claimed
until the replacement remote run finishes. Integrity tests cannot qualify contact
pressure, preload, strength, physical fit or continuous motion; all acceptance flags
remain false and the original eight fastener support failures remain intact.
