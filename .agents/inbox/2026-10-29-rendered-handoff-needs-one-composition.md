# Matching image and canvas dimensions does not align different compositions

On 2026-10-29 UTC, the user reported an odd loading overlay and yellow-on-yellow hero. The old `/docs/hero.jpg` was a 2048×939 promotional CAD sheet with text, one leg and a separate bench turret, while `web/landing.js` rendered the complete robot. The script hid the image before its first rendered frame. Matching CSS width/height did not fix that content difference.

A first corrective screenshot still showed a yellow hero after the early `.hero-scene` rule was changed to blue. `rg -n 'hero-scene' web/landing.css` exposed a later radial-gradient override (`#fff5bd`, `#ffe191`, `#ffd66c`). The screenshot, not the edited declaration, revealed the surviving conflict.

Correction: capture the actual current hero scene as a transparent square poster, use one reference camera and aspect-aware projection, wait for a completed frame before revealing WebGL, and fix the final computed background rule. The existing build now runs `tools/test-hero-preview.mjs` through its registered test entry, with delayed-import and failed-WebGL paths plus pixel/silhouette comparison across sizes. Evidence outputs are under `/tmp/gyropup-hero-preview` during local runs and CI artifacts when the suite runs there.

The next screenshot pass caught pale shared `.gp-text` coloring inside the light landing bubble. Setting only the bubble parent's color did not override the child rule. Landing-scoped theme tokens now color the child text, caret and tail consistently; the greeting regression checks at least 4.5:1 text contrast.

Dated command evidence from 2026-10-29 UTC, before the final contrast addition:

```text
$ SITE_URL=http://127.0.0.1:8890 node tools/test-hero-preview.mjs
PASS chromium: visible poster/first-frame match at12 viewport/DPR combinations; delayed loading; module/WebGL fallback; hover, keyboard, touch inspection; shared audio and reduced motion
```

The later normal-motion screenshot was the evidence that exposed the child-color problem despite those passing geometry checks. Keep both measured checks and visual review; neither substitutes for the other.

The durable procedure is [Landing preview](../domains/landing-preview.md). This checks sampled software presentation; it does not prove subjective appeal or hardware geometry correctness.
