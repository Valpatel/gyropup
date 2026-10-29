# Parts retain their identity when their table changes

Gyropup's Build and Progress checklists use the shared cad-agent table/tracker modules unchanged. Update those modules from an identified toolkit commit, and put product wiring in `designer/portal-parts.js`. Report toolkit defects upstream instead of patching a divergent product copy.

Stable status keys describe catalog parts, manufactured parts or scoped print parts. Sorting, filtering, seller grouping and workstream inclusion must never change those keys. Dispose old table enhancers before replacing report nodes; otherwise old tracker subscriptions survive and toolbars/status columns can duplicate. Use raw source numeric values in `data-sort-value`, with empty values for unknowns. Do not parse arbitrary formatted labels or move fixed totals through the sort.

The published-model inventory is generated from tracked files inside the existing public roots. It intentionally differs from all tracked CAD: the27 Upkie reference STLs in `rl/vendor/` are not published. Keep original download addresses and add preview affordances around the web UI; do not rewrite CAD or report data to viewer URLs. Scoped media keys and source links follow [part image identity](part-images.md).

`tools/test-build-portal.mjs` exercises actual native controls, cross-page persistence, invalid imports and denied storage, numeric/text sorting and all published original/preview mappings. `tools/test-markdown.mjs` protects the validated published-data snapshot. Parser corpus validation remains separate from link coverage. See `docs/validation/build-portal.md` for the integration contract and limits.
