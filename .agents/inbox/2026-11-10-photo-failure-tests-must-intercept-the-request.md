# Arm an image-failure fixture before the browser can load the image

On 2026-11-10, PR #283 at `7a3222ac8fe4f9d3b01798d483e3441f0eddc1e2`
failed the build-portal browser job while waiting for the PETG source-link fallback.
The [original CI log and artifacts](https://github.com/Valpatel/gyropup/actions/runs/42842363492/job/129920648779)
retain the 60-second timeout, an empty page-error list, and a screenshot showing a
successfully loaded product photo. The route was registered after navigation and
table readiness. A lazy image may already have loaded; intercepting a later request
cannot retroactively fail that completed request.

Independent Chrome and WebKit controls reproduced all three cases: an image
fulfilled before registering the abort stays visible with no failed request;
an abort registered before navigation produces the original supplier source link;
disabling the real image error handler leaves a broken image and fails the fallback
expectation. Six cases passed against the unchanged product implementation.

The existing `tests/site/content/test-build-portal.mjs` now installs the route before
navigation, requires both an interception and an actual `requestfailed` event, and
retains those observations in success/failure reports. Run that existing test with
`SITE_URL` set to its owned test server in both browser engines; the full build-portal
suite still checks the original table, download, preview and mobile behavior.

Do not retry this race to green, lengthen its timeout, or alter the product fallback
to satisfy an untriggered fault. A fallback assertion needs evidence that its real
failure stimulus occurred. These controls qualify photo fallback only; they do not
redesign the queued BOM or print-queue tables (#281).
