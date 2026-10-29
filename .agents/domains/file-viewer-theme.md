# The original-file viewer uses the product palette through generic theme tokens

The shared cad-agent viewer exposes `theme` / `setTheme` and `--file-*` tokens
(upstream issue #73 / PR #75). Gyropup owns its palette in
`web/file-viewer-theme.css`: the landing page's cream, deep teal, rust and local
Inter font. The standalone HTML defaults to light, links the consumer stylesheet
after the generic stylesheet, and returns to the build portal when no explicit
same-origin back link was supplied. A query can still select generic dark or auto.

Keep the shared viewer's file parsing, original download URL and geometry intact.
Do not add Gyropup names/colors to the upstream component. Copy its viewer changes
deliberately: this project's `stage.js` additionally owns smooth-wheel zoom,
short-landscape framing, sky dimming and animation disposal fixes. Theme support
is an additive palette method, not a replacement of those product adaptations.

Validate real Chromium/WebKit desktop and phone rendering, visible text/control
contrast, local-only dependencies and loading/error states. Theme updates must
preserve model materials and camera pose. Neither a visual preview nor a theme
implies current mechanical or print qualification.
