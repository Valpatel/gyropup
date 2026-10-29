# Network fixtures must prove they matched versioned resources

On 2026-10-29, independent review of PR112 found that the highlights harness's
intended failed/held hero fixture did not intercept the hosted hero module.
The static build had appended an asset version query. Normal playback results
were real, but the claimed failed-hero isolation was not exercised by that fixture.

The review compared these Playwright route predicates against the immutable
Cloudflare build at `61503da61ba4ec9fb705d755a4566de9249a0d7a`:

```text
page.route('**/web/landing.js', handler)
fixture hits: 0; real hero reached ready

actual request:
/web/landing.js?v=2ae4026f3475a471b67b

page.route(url => url.pathname === '/web/landing.js', handler)
fixture hits: 1; hero remained in the intended held state
```

Evidence is attached to the review finding on
[PR112](https://github.com/Valpatel/gyropup/pull/112#discussion_r4417377207).
The intended failure and actual network request were never compared, so a
successful unrelated playback assertion could be mislabeled as failure coverage.

Match the resource pathname when cache-version queries are irrelevant to the
scenario. Also assert that the fixture ran and that the intended held, failed or
missing state actually occurred before testing recovery. A permissive route alone
is not evidence of injection. `tools/test-highlight-video.mjs` carries those
assertions with the correction; no production import or cache-version behavior
is removed to make the tests pass.

This finding invalidates the earlier hosted fixture's isolation claim, not its
actual video decode, viewport, or replay observations. Real-hero integration is a
separate test and still requires actual imports and model downloads.
