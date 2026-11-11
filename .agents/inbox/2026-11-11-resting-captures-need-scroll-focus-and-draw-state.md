# Resting screenshots need observed scroll, focus and draw state

On 2026-11-11 UTC, the homepage typography check at `2066e779` passed real
rendered-text, responsive-break, keyboard and seeded DOM-negative assertions in
Chrome and WebKit. Root rejected its full-page images as resting visual evidence:
the driver had scrolled `#play-title` into view before capture, and the images
showed a displaced skip link or blank desktop hero. The initial reports recorded
BODY focus, but did not record scroll position or actual renderer work. Keep the
functional success and the rejected visual evidence distinct. The exact browser
capture mechanism was not localized; this did not justify a product CSS fix.

The separately reviewed capture-only action reset top scroll and focus, observed
the real canvas and used the existing hero export hook. Dated command/output:

```text
2026-11-11 UTC
node /tmp/gy313-rest-2066e779.mjs --controls
PASS capture preconditions: positive plus retained-scroll, visible-skip, focus, blank/nonadvancing/empty-frame negatives

Retained actual reports, immediately before full-page screenshot:
Chrome 320: scrollY=0 BODY skip.bottom=-32 frames=3->4 triangles=347051 opaquePixels=15429
Chrome1440: scrollY=0 BODY skip.bottom=-32 frames=7->8 triangles=347051 opaquePixels=28424
WebKit 320: scrollY=0 BODY skip.bottom=-32 frames=2->3 triangles=347051 opaquePixels=15434
WebKit1440: scrollY=0 BODY skip.bottom=-32 frames=5->6 triangles=347051 opaquePixels=28423
Both: errors=[] sourceUnchanged=true listenerClosed=true exit=0 MainPID=0; cgroup absent and TCP refused.
```

The [capture action review](https://github.com/Valpatel/gyropup/pull/314#pullrequestreview-5853978777)
and `plans/public-entry-closeout/resting-captures.json` retain source, invocation
and report identities. Root independently inspected all eight resulting PNGs.
Prior functional reports, rejected images and a prelaunch argument rejection
remain historical; none is overwritten or reclassified as product failure.

Define the capture purpose first. For a resting entrance, separately prove
keyboard behavior, then explicitly blur and return to document top. Assert
scroll position, active element and skip-link bounds before and after capture.
Wait for actual fonts and canvas presentation. A ready flag alone does not prove
a drawn image: retain renderer frame advancement, triangles and decoded alpha
coverage when using the existing export hook. Record when that hook explicitly
renders; it is not proof of a naturally advancing offscreen animation. Preserve
capture state/errors and review the actual PNGs before visual acceptance.

A full-page capture does not hydrate every lazy offscreen image. The phone's
offscreen reel poster remained unhydrated at top rest, so these PNGs do not
establish reel appearance or playback. Keep separately exercised reel tests and
source-bound media validation. The capture preconditions change evidence scope,
not product layout, accessibility, render correctness or physical qualification.
