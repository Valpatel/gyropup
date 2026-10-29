# The landing poster is a rendered frame, not a second illustration

The hero poster comes from `tools/render-hero-poster.mjs` using the actual current model, lighting and initial pose in `web/landing.js`. A fixed reference camera with aspect-adjusted field of view makes its square transparent image and the canvas share the same composition at every viewport. Keep both in the same positioned box. Reveal WebGL only after the first complete frame; preserve the image when imports or WebGL fail.

After changing current robot geometry, materials, lighting, camera or initial pose, build, run `SITE_URL=<preview> node tools/render-hero-poster.mjs`, and build again. Commit the generated poster with its source changes. Do not substitute a promotional image or historical CAD sheet: matching outer dimensions cannot make different compositions align.

`tools/test-hero-preview.mjs` compares actual rendered silhouette and pixel color with the poster at desktop, narrow portrait and short landscape sizes and DPR1/2. It also checks delayed loading, failure fallback, inspection controls, reduced motion and shared sound. Inspect the screenshots: a passing box-size assertion alone misses visible mismatch.

Read computed styles and actual screenshots when changing the palette. Existing styles may override an earlier declaration. The hero's measured cool background is part of the regression, so another late yellow override cannot silently undo the change.

Hover inspection is optional presentation; touch and keyboard have an explicit button. Landing speech uses the shared master enabled/volume settings, remains silent until a user gesture, and cancels when hidden. The visibility test uses a deterministic input adapter; it is not proof of every browser's native background-tab policy.

On 2026-10-29, the integrated branch passed `SITE_URL=http://127.0.0.1:8890 npm run test:hero` in Chromium and WebKit. Each engine covered six viewports (320×568 through 1440×1000, including 844×390 landscape) at DPR1/2. The minimum poster/render silhouette overlap was 0.9904 Chromium / 0.9807 WebKit; maximum mean RGB error was 1.967 / 2.799 out of 255, below the test's 8 threshold. Both also passed normal-motion first-frame alignment, the visible greeting's 4.5:1 contrast guard, mute/volume, repeated hover, touch/keyboard inspection and hidden-clock input checks. CI retains actual loading/ready/greeting/fallback screenshots and JSON measurements as presentation evidence artifacts. Re-run on the final built revision; these local measurements included then-uncommitted integrated source changes.
