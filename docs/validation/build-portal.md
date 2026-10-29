# Build portal interaction contract

Issue #53 refines the existing Build and Progress portal. It does not change part selection, quantities, pack rounding, supplier preferences, recorded engineering results, or the simulation models.

| Area | Earlier behavior | Required behavior |
| --- | --- | --- |
| Order overview | Long explanatory paragraphs and expanded supplier grids | Short totals, workstream choices, section links, expandable supplier lists and sourcing details |
| Parts and reports | Grid rows or static tables | Semantic tables with explicit numeric source values, visible sort controls and search where there is more than one row; fixed totals stay outside sorting |
| Build status | No persistent checklist | Ordered/in-hand part statuses and printed status, shared across matching Build/Progress identities; local-browser scope explained beside native export/import controls |
| Re-rendering | Replacing row markup could detach tracking | Dispose table enhancers before replacing their nodes; state keys describe parts, never row indices or current display order |
| Images | Missing-ID dumps, unscoped names and private-photo assumptions | Stream-scoped CAD images, verified supplier image URLs with source links, and readable failure links without publishing ignored assets |
| Original CAD files | Download-only anchors | Adjacent interactive preview and original download; original JSON/CAD URLs unchanged |
| Agent Markdown | Generated published-data snapshot | Same validated bundle data and semantic row content; UI enhancement is explicitly adapted, never simulated with checkout-local data |

The table/tracker source is copied unchanged from cad-agent PR #63: `part-table.js` at `9138622`, and `part-tracker.js`/`part-table.css` at `4f74917`. Gyropup's `designer/portal-parts.js` supplies project identity, status columns and disposal. It hides redundant controls for one-row groups. The project key is `gyropup`; fields are `ordered`, `inHand`, and `printed`. Part status is not a quantity ledger, purchase submission or synchronized shared inventory. Invalid imports are atomic. Unavailable storage retains in-tab changes and presents an export reminder.

Build and Progress reuse catalog identities (`buy/<catalog-key>`), scoped manufactured identities (`made/<stream>/<part>`) and scoped print identities (`print/<stream>/<part>`). Repeated Progress BOM rows for one catalog identity are grouped without dropping their quantities or purpose notes. Historical motor-note prices only receive numeric sort values when the source uses explicit dollar notation; other formats remain unknown rather than being guessed.

`site/models.json` inventories the 495 original model files already inside the published roots: 288 STL, 188 STEP and 19 3MF. Every published directory entry and existing document anchor receives a preview affordance; a shared browser helper adds the same affordance to dynamically rendered parts. The 27 tracked Upkie reference STLs under `rl/vendor/` remain outside the publication boundary. This change does not publish those reference assets or ignored vendor CAD/photos.

## Verification

Build a coherent preview, then run:

```sh
npm run build
SITE_URL=http://127.0.0.1:8893 node tools/test-build-portal.mjs
PLAYWRIGHT_BROWSERS_PATH=/tmp/gyropup-security-browsers PLAYWRIGHT_BROWSER=webkit SITE_URL=http://127.0.0.1:8893 node tools/test-build-portal.mjs
npm run test:markdown
npm run test:part-media
```

The product harness checks numeric/text sorting, part identity across filtering/reordering/include changes/reload, matching statuses across Build and Progress, printed status, native export and atomic import, denied storage, original/preview mappings for all 495 published models, fixed totals, and phone portrait/landscape layouts. Reports include the preview build version. Representative original STL, STEP and 3MF files must open through real directory preview links; camera zoom is observed until its eased target, and stage stop/resume/disposal must stop callbacks and release its canvas/context. The viewer runtime comes from cad-agent `e283ff3`, with parser/vendor assets from `d6b4b8e`. Gyropup adds the missing stage stop/dispose lifecycle without replacing its custom rendering behavior. Local serving maps WebAssembly to `application/wasm`. The original-file viewer's parser corpus and worker failure checks are owned by the shared toolkit suite; mapping coverage alone is not evidence that a CAD parser can open a file. Final receipts belong on PR #54.

Limits: checklist fields are Boolean part statuses, not purchased/printed unit counts. Recorded prices remain estimates until a supplier quote or checkout confirms them. Verified remote product images can later be unavailable, so the page retains source links. Browser previews do not establish physical manufacturability or validate CAD/FEA engineering conclusions. Hosted deployment is a separate versioned check.
