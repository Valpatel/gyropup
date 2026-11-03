# The original-file viewer uses the product palette through generic theme tokens

The shared cad-agent viewer exposes `theme` / `setTheme` and `--file-*` tokens
(upstream issue #73 / PR #75). Gyropup owns its palette in
`web/file-viewer-theme.css`: the site's light set (warm white, navy ink, sky canvas, local Inter font)
and its dark set (the valpatel.com void, light ink, cyan focus and accent).
The standalone HTML follows the site's theme (`web/theme.js`: the system setting or
the reader's stored choice) and switches with the header's theme button. It links the
consumer stylesheet after the generic stylesheet, and returns to the build portal when
no explicit same-origin back link was supplied. A `?theme=light|dark|auto` query
keeps its own theme and ignores the button.

Keep the shared viewer's file parsing, original download URL and geometry intact.
Do not add Gyropup names/colors to the upstream component. Copy its viewer changes
deliberately: this project's `stage.js` additionally owns smooth-wheel zoom,
short-landscape framing, sky dimming and animation disposal fixes. Theme support
is an additive palette method, not a replacement of those product adaptations.

Validate real Chromium/WebKit desktop and phone rendering, visible text/control
contrast, local-only dependencies and loading/error states. Theme updates must
preserve model materials and camera pose. Neither a visual preview nor a theme
implies current mechanical or print qualification.

The hosted navigation regression must accept the local `.html` route and its
Cloudflare extensionless canonical route after a native click, while requiring
the same origin and exact destination path. Do not replace navigation with a
direct `goto` or ignore a failed assertion. Original download/href checks remain
strict. See [the canonical-route incident](../inbox/2026-10-29-hosted-navigation-must-accept-the-canonical-route.md).

Inspect the actual imported assembly's member names and material assignments. A compound export can erase distinctions between physical parts and reservations even when the viewer is correct. `tools/test-carrier-inspection.mjs` binds the served STEP to its committed receipt and checks the current bounded carrier's named mounting instances, semantic colors and native navigation, with actual-scene corruption controls. Its explicit inventory is that carrier checkpoint's contract, not a substitute for full BOM coverage. Preserve terminal reader states and failure captures; a later passing retry does not explain an earlier timeout. See [the imported-assembly incident](../inbox/2026-10-29-review-the-imported-assembly-not-only-the-export.md).
