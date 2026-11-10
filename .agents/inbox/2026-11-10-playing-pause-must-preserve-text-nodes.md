# A genuine pause must preserve existing playback text nodes

2026-11-10, PR #286, built source `2949ccc3`.

The idempotent renderer fixed stopped and already-paused controls but a genuine
playing→paused transition still replaced Play/status text nodes and the SVG path.
In native WebKit, after real hip selection/close, section z, Flip, depth .4,
Play/Pause, paused Flip/Rotate, Play/Flip, Play/Loop/Rotate, the final Rotate missed:
trusted pointerdown y665 / scroll202, pointerup y692 / scroll175, click on its
container. The shared player did pause, but section x never rotated to y.
CI run `42875931873`, docking job `130039207319`, independently matched it.

A bounded measurement around that exact activation found status height16px,
content clientHeight383, scrollHeight585 and maxScroll202 on both sides of pause.
Status text changed Installing→Paused without wrapping. It moved from y377 to
404 as scrollTop fell202→175, bringing the changed status to the scroller top.
This excludes the proposed height/wrapping/clamp explanation. Failure traces,
measurement and original hashes are in
`plans/instruction-docking/playing-2949/`. Portal job `130039207323` failed earlier
at the expected stale poster binding, before any browser phase; it is distinct.

Update an existing sole text node through `nodeValue`, and update the existing
SVG path's `d` attribute. Keep unchanged writes idempotent. Do not replace these
nodes during the host-capture pause, intercept native focus, synthesize clicks or
freeze status layout to hide a failure. Check actual stopped, paused and playing
states with trusted pointer phases, preserved section state, and actual stopped
time; retain normal keyboard and touch behavior. A diagnostic that forces layout
between native writes may mask the bug and cannot substitute for the native flow.

This establishes the observed browser boundary, not a general claim about every
WebKit scroll implementation. The existing keyboard/touch and layout checks
remain required independently of text-node identity diagnostics.
