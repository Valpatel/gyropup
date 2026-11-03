# Light and dark themes come from one token file

`web/theme.css` holds every page colour as a `--gp-*` token: a light set on `:root`, and one dark set written twice
(under `@media (prefers-color-scheme: dark)` on `:root:not([data-theme=light])`, and on `:root[data-theme=dark]`).
The two dark blocks must stay identical. The light set is the friendly, bright look: warm white, navy ink, sunny
yellow, sky blue, coral and mint. The dark set is valpatel.com's mission-control look: the void `#0a0a0f` and its
surfaces, cyan hairlines, green/amber/magenta status. The dark theme's decorative layer sits at the end of
`web/theme.css`, written twice like the token block (`tools/test-theme.mjs` checks the copies match): a hairline grid
on `body`, void panels for the motto and the status strip, a glowing status dot (in `:where()`, so a page's own dot
colour wins), and corner brackets as an `::after` 10 px inside the main panels' edges (clear of their rounded
corners). A bracket is never part of a panel's background, so the contrast scan still sees what is behind text. Page stylesheets (`web/*.css`, `designer/**/*.css`, the inline `<style>`
blocks and the app bar's CSS in `designer/kit/appnav.js`) use `var(--gp-*)`, or a local alias of one (`--ink`,
`--text`, `--sb-ink`, ...). `*-rgb`, `--gp-shadow` and `--gp-hi` are RGB triples for `rgb(var(--gp-…) / alpha)`.

`web/theme.js` is a classic script loaded first in `<head>`, then `web/theme.css`, on every page; the build fails if a
built page does not. It sets `data-theme` on `<html>` from `localStorage['gyropup-theme']` before anything paints,
handles every `.theme-toggle` button by one delegated click listener (the app bar is drawn later by a module), forgets a
choice that matches the system, and sends nothing anywhere. It dispatches `gyropup:themechange` on `document` after a
press or a system change; listeners redraw what CSS cannot reach.

What keeps its own colours in both themes, on purpose: the always-dark surfaces (the motto banner, the status board's
navy strip, the safety notice's navy action bar and hazard stripe, the dark hero/loop buttons), saturated fills under
white text (orange buttons; use `--gp-accent-fill`/`--gp-ink-fill` for a fill under white text), status colours used
as fills, and 3D material colours. A translucent dark or white literal on an always-dark surface must stay literal: a
token there turns light in the dark theme (the notice backdrop and the timeline's picture labels did, in review).

Canvas and drawings:
- `designer/kit/stage.js` takes its sky from `--gp-stage-sky` and follows theme changes until a caller sets its own
  background (`setPalette({background})`, `setSceneBackground(day)`); `setSceneBackground()` with no arguments returns
  to the page sky. `designer/sim.js` paints the yard from `--gp-stage-ground`.
- The landing hero's canvas is transparent over the `.hero-scene` gradient (sky tokens). Its light value is exact:
  `tools/test-hero-preview.mjs` checks `220, 238, 255`.
- The file viewer follows the site theme unless a `?theme=` query is given (see `file-viewer-theme.md`).
- Mermaid is drawn in the browser (`designer/kit/diagrams.js`), so each diagram is drawn in the page's theme and drawn
  again, once per theme, when it changes (`refreshDiagramThemes`). The figure frames in `diagrams.css` are literal,
  because the frame must match the theme the SVG was drawn in, not the page's current one.
- Renders drawn on white (`.document article img`) sit on a `--gp-image` panel in the dark theme instead of being
  re-rendered.

Checks: `npm run test:theme` (token parity, key pairs at 4.5:1 in both themes, load order, the button and its stored
choice, no flash with a held stylesheet, every visible text run's contrast against what is behind it on the main
routes at 360 and 1366 px in both themes, no sideways scroll, scenes, viewer and diagrams following the theme).
Look at real screenshots in both themes as well: the contrast scan skips text inside SVG, canvas and video.
