# Published Markdown needs actual diagram rendering

On 2026-10-29 the production `/site/pages/docs-architecture-md` page (“How Gyropup is engineered”) showed raw Mermaid text. A Chromium probe against production c9229dd found one visible Mermaid code block, zero article SVGs, and zero diagram scripts. `tools/build-site.mjs` rendered Markdown headings and links but never loaded a diagram renderer. The same gap affects all three diagrams in `research/power-electronics.md`.

Corrective rule: wire the shared cad-agent diagram helper into the actual production document frame and self-host its pinned runtime. Test every published Mermaid-containing document for SVG geometry/labels and hidden default source. Test dynamic Markdown insertion, both browser engines, phone containment, matching theme, held/failed downloads and retries. A Markdown-route/source assertion alone cannot prove the HTML consumer works.

Source stays available in a closed disclosure and the original Markdown route. Loading and errors have visible text and recovery controls. These tests establish browser presentation only, not the validity of the engineering diagram or underlying design. Pending mechanical branches are excluded from this production hotfix.

Independent visual review found native-width diagrams could appear clipped without a visible scroll cue. The shared helper now shows an overflow-only sideways-scroll hint and refreshes it after viewport resizing. Regression checks scroll to the rightmost semantic node; readable labels alone do not establish that the whole diagram is discoverable.
