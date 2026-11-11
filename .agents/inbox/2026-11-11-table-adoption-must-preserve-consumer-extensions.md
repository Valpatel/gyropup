# Compare consumer table extensions before adopting a shared replacement

On 2026-11-11, a provisional full-file adoption from the shared toolkit dropped the product’s existing generic `pageSize` and `setFilter` API. Review of `git diff HEAD^ HEAD -- software/site/designer/kit/part-table.js` at candidate `60a9f7a4` showed the removed pagination navigation and filter predicate; this was caught before browser validation or publication. Syntax checking alone had passed because the removed API was only exercised at runtime.

Cause: the consumer already carried useful table extensions that were absent from the shared source. Copying the newer shared file did not imply a compatible superset.

Corrective rule: compare both versions’ exported APIs and consumer calls before adoption. Move generic extensions to the toolkit, keep the product copy byte-identical to the reviewed shared implementation, and exercise consumer filters, hidden pages, stable checklist identity and all-page output together. The printable-checklist regression now requires all matching rows even when the screen shows another page, and checks the live row/page/status state remains unchanged after printing.

Limits: this incident concerned table behavior, not CAD data, geometry or manufacturing readiness. Toolkit release adoption and independent review still precede publication.
