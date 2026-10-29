# A bounded CAD check still needs the full input closure and valid Boolean results

On 2026-10-29 independent PR #67 review reproduced two false-green paths in the new carrier checker at8b86e7f. A scratch change to `cad/interfaces.json` raised M5 clearance from5.5 to7.5 mm, affecting the pan base, but all four source guards passed because only five manually listed files were bound. A controlled invalid open-solid Boolean returned raw CadQuery `Volume()==0`; the product's `overlap()<1e-6` accepted it as clearance. The reviewed toolkit validator rejected that same BREP.

Verified findings: [missing dependency](https://github.com/Valpatel/gyropup/pull/67#discussion_r4411664197), [invalid Boolean](https://github.com/Valpatel/gyropup/pull/67#discussion_r4411664406). These were defects in the bounded checker, not new evidence about printed fit or a reason to relax tolerances.

Correction: reuse `print_provenance.snapshot` for the complete CAD/config/catalog/design Python/JSON closure, optional parameter identity, runtime and toolkit fingerprint. Capture before geometry imports, compare again at completion, and compare the entire file set in the kernel-free guard. Changed, removed and newly added inputs must invalidate a receipt. Use the reviewed public `relate` predicates for topology, uncertainty and volume conservation; an unknown result stops the candidate rather than becoming zero. Preserve the original overlap/difference budgets.

A second review of WIP 1f03d27 found that summing thresholded pair results expanded the aggregate allowance: two actual 0.6e-6 mm³ contacts each became zero, hiding their 1.2e-6 mm³ sum. Allocate the single total budget across all pairs before classifying them, retain each allocation, and never describe a thresholded result as measured common volume. Equal conservative shares can reject uneven overlaps that would fit the total; that limitation is intentional and does not increase acceptance.

Independent recheck of 36aa696 then caught an equality edge: two protected-region outside volumes exactly 0.5e-6 mm³ each were accepted by inclusive half-budgets, whereas the former total test was strictly `< 1e-6`. Allocate one floating-point step below each equal share for both clearance and protected-region checks. Test exact equality, a below-limit control and actual integration-error estimates through the real relation decision path; a canned unknown-result test alone does not exercise that boundary.

Committed reproductions:

```sh
python tools/test-base-board-interface-geometry.py
python tools/test-base-board-interfaces.py
```

The first suite uses real overlapping/disjoint boxes and an invalid open solid, plus clipped-region, numerical-unknown, aggregate-budget, strict-equality and integration-error controls. It runs under the separately pinned v0.4.2 source at 2ad4269. The second includes changed M5 clearance, deleted `gmi.py`, added input and recorded-allocation cases. Full corrected candidate evidence and the independent recheck belong to the source-hashed interface receipt and PR review, not this note.

Limits: even valid bounded relations do not establish connector retention, wire bends, electrical isolation, physical tolerances or strength. Separate `readiness:false` remains required while those inputs are absent. Never replace this distinction with a blanket intended-overlap exception.
