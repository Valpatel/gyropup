# Sticky part identity needs the scroll wrapper to own overflow

On 2026-10-29, the Build portal's 320px table allowed both status checkboxes to be reached, but their part names scrolled offscreen. Adding `position:sticky; left:0` to the Part column initially did not fix it. The existing `table.cmp { overflow:hidden }` became the nearest overflow ancestor, so the cell moved with the table instead of sticking to `.cad-table-scroll`.

The focused native-browser regression measured the fully scrolled made-parts table:

```text
node tools/test-build-portal.mjs
before: identity x=-676.84375, right=-556.84375
Ordered: x=133.1875, width=77.40625, height=44, reachable=true
In hand: x=222.59375, width=77.40625, height=44, reachable=true
after: PASS chromium; identity visible inside the first 160px;
both status labels >=44px, inside the viewport, and reachable by elementFromPoint
build assets: 68dc8e0f08fd5993634d
```

The fix scopes `overflow:visible` to enhanced tables and leaves scrolling/clipping with the wrapper. Product CSS gives the identity column 120px on phones and reserves the remaining width for both status targets. The harness checks actual projected rectangles and hit targets, not only computed sticky styling; it saves `chromium-status-320.png` and the corresponding WebKit screenshot for visual review. The first passing receipt above is Chromium; the final merged branch still receives both engine checks.

Corrective rule: when a sticky table cell fails, inspect overflow ancestors before changing offsets or widening the viewport. A checkbox that can be clicked is not sufficient if its row identity has disappeared. Durable guidance is in [the parts portal domain](../domains/build-portal.md).

Limits: this check covers this portal's tracked tables and native 320px layout, not arbitrary nested tables or browser zoom settings. Local status checks remain Boolean part identities, not unit quantities.
