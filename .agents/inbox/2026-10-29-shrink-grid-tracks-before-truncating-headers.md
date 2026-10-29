# A narrow header can widen the whole viewer despite hidden page overflow

On 2026-10-29 UTC, the integrated loading/notice browser suite failed `viewer-http: retry in viewport` at 320 × 568. An explicit CAD manifest supplied a longer title; adding the notice control made the mobile grid's intrinsic minimum wider than the viewport. The body clipped overflow, concealing the missing controls instead of making them fit.

Measured with a real HTTP503 mesh response in Chromium:

```text
before: HUD width 320; topbar/stage width 395.609; Retry right edge 376.602
after:  HUD width 320; topbar/stage width 320; Retry right edge 301
```

Use `minmax(0, 1fr)` for the narrow HUD grid track and `min-width: 0` for its header. Ellipsis on a flex child cannot by itself override the enclosing grid's automatic minimum. Check actual control bounds/hit targets in failed and pending states, not only `document.scrollWidth` or a successful scene.

The existing `tools/test-loading-portal.mjs` failed-response/phone case is the regression. This is a CSS layout finding; it does not alter model geometry or establish hardware safety.
