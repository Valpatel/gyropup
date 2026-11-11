# Compare consumer table extensions before adopting a shared replacement

On 2026-11-11, a provisional full-file adoption from the shared toolkit dropped the product’s existing generic `pageSize` and `setFilter` API. Review of `git diff HEAD^ HEAD -- software/site/designer/kit/part-table.js` at candidate `60a9f7a4` showed the removed pagination navigation and filter predicate; this was caught before browser validation or publication. Syntax checking alone had passed because the removed API was only exercised at runtime.

Cause: the consumer already carried useful table extensions that were absent from the shared source. Copying the newer shared file did not imply a compatible superset.

Corrective rule: compare both versions’ exported APIs and consumer calls before adoption. Move generic extensions to the toolkit, keep the product copy byte-identical to the reviewed shared implementation, and exercise consumer filters, hidden pages, stable checklist identity and all-page output together. The printable-checklist regression now requires all matching rows even when the screen shows another page, and checks the live row/page/status state remains unchanged after printing.

Limits: this incident concerned table behavior, not CAD data, geometry or manufacturing readiness. Toolkit release adoption and independent review still precede publication.

## Compare real visible boxes, not equal zero-size deltas

On 2026-11-11 the provisional planner report recorded zero header/cell edge deltas for Find a part while the Print panel was selected. Source inspection (`build.html` places `#made` under `data-build-panel="buy" hidden`) showed that both compared boxes could be hidden and zero-sized. Queue was in the active Print panel and its shifted-header negative control did fail as intended; that did not establish visibility for a different table.

Cause: the harness compared relative deltas without proving that each target was displayed. Corrective rule: activate the table’s actual native panel, require positive header and body-cell widths, then compare both column edges. Keep an actual shifted-header rejection control. The committed test now does this for both tables; the provisional hidden-table result remains explicitly unaccepted until the corrected test executes. Limits: this is layout evidence, not a manufacturing or full viewer acceptance claim.
