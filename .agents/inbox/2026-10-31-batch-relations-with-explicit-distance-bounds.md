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

The first replacement producer used one table per ring with `only=[ring]`, explicitly
retrieves all 59 required relations, and keeps the original eight candidates and
default tolerances. It recorded exact toolkit bounds and posed shape identities.
Remote `apart` rows are lower-bound evidence (`exact: false`); all pairs whose
boxes are within 1 mm remain exact. Actual motor-plate contact must be exact and
positive. Tables' ordinary iteration/JSON export omit broad-phase rows, so they
cannot replace the explicit required-pair inventory.

That revision’s kernel-free guard independently recomputed AABB separation. It rejected
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

## Follow-up: measure the hot call before another optimization

The replacement table run also stayed on its first candidate for more than
20 minutes. A bounded, independently instrumented remote diagnostic used the same
frozen `4675c2c` source and released toolkit. Process-local timing wrappers preserved
all original return values; no shared installation was edited. It reported:

```text
2026-10-31 UTC; diagnostic-independent-4675c2c/diagnostic.log
elapsed 35.312: Assembly complete (60 validated single-solid parts)
elapsed 57.668: first exact pair, ring versus manufacturer solid 09203744…
elapsed 57.673: ring adaptive volume complete (0.0049s)
elapsed 57.673: manufacturer-solid adaptive volume begins
60s stack dump: relations.py:584, BRepGProp.VolumePropertiesGK_s
```

The separately recorded enclosing-box gap for that fastener is 0.21 mm. Of the
29 manufacturer candidates under the original 1 mm margin, 24 already have proved
box gaps of 0.1 or 0.21 mm, exceeding the unchanged 0.01 mm touch classification. The
hot call is unnecessary for their nominal no-contact classification; table-level
memoization alone cannot eliminate each unique fastener's first integration.

The revised research policy explicitly sets the broad-phase near margin to 0.01 mm,
with all other released tolerances unchanged. Every requested pair remains in the
report, bounds retain their inexact label, and exact plate contact stays mandatory.
Tests require exact queries for boxes within that margin and reject an inexact
0.005 mm or exactly 0.01 mm bound. A 0.02 mm bound can establish nominal apart status;
it does not establish manufacturing clearance, dynamic clearance or physical fit.
The source/context receipt records the new policy. Older diagnostics are retained,
not relabeled as completed evidence. No new speed or clearance result is claimed
until the new actual run completes.
