# Compare consumer table extensions before adopting a shared replacement

On 2026-11-11, a provisional full-file adoption from the shared toolkit dropped the product’s existing generic `pageSize` and `setFilter` API. Review of `git diff HEAD^ HEAD -- software/site/designer/kit/part-table.js` at candidate `60a9f7a4` showed the removed pagination navigation and filter predicate; this was caught before browser validation or publication. Syntax checking alone had passed because the removed API was only exercised at runtime.

Cause: the consumer already carried useful table extensions that were absent from the shared source. Copying the newer shared file did not imply a compatible superset.

Corrective rule: compare both versions’ exported APIs and consumer calls before adoption. Move generic extensions to the toolkit, keep the product copy byte-identical to the reviewed shared implementation, and exercise consumer filters, hidden pages, stable checklist identity and all-page output together. The printable-checklist regression now requires all matching rows even when the screen shows another page, and checks the live row/page/status state remains unchanged after printing.

Limits: this incident concerned table behavior, not CAD data, geometry or manufacturing readiness. Toolkit release adoption and independent review still precede publication.

## Compare real visible boxes, not equal zero-size deltas

On 2026-11-11 the provisional planner report recorded zero header/cell edge deltas for Find a part while the Print panel was selected. Source inspection (`build.html` places `#made` under `data-build-panel="buy" hidden`) showed that both compared boxes could be hidden and zero-sized. Queue was in the active Print panel and its shifted-header negative control did fail as intended; that did not establish visibility for a different table.

Cause: the harness compared relative deltas without proving that each target was displayed. Corrective rule: activate the table’s actual native panel, require positive header and body-cell widths, then compare both column edges. Keep an actual shifted-header rejection control. The committed test now does this for both tables; the provisional hidden-table result remains explicitly unaccepted until the corrected test executes. Limits: this is layout evidence, not a manufacturing or full viewer acceptance claim.

## Staying inside PDF bounds does not establish readable numeric cells

On 2026-11-11 independent review of the real A4 queue PDF found short headers split midword and a numeric value split across lines. The first interpretation attributed a trailing `6` to Hours `72.5`, but subsequent bounding-box/source inspection located it in the preceding Grams column: actual hip-frame mass `1106` was split into `110` / `6`. The initial `72.56` test failed against the actual source and was corrected to exact same-row Grams `1106` and Hours `72.5`. The prior page-bound audit still passed because every fragment remained inside the page. Character-count width weights and unrestricted word breaking had treated numeric/status columns like free-form descriptions.

Corrective rule: preserve semantic numeric/status column types, reserve intrinsic widths and prohibit wrapping for compact data and short headers. Permit wrapping in IDs/descriptions and use landscape for dense lists while retaining the paper choice. Verify compact-cell line ranges at actual printable A4/Letter widths and inspect the actual PDFs for whole numeric/header tokens as well as complete IDs, repeated headers and page bounds. Retain the failed observations; a generic 75-row fixture alone does not prove the real product table readable.

A related source audit found `Model export pending` on 21 real turret rows lost when a plain part label replaced the interactive cell text. Printable identity text now retains row-specific small notes and marked qualification warnings, including oversized-bed warnings from an omitted setup column. No missing STL is invented or enabled.
