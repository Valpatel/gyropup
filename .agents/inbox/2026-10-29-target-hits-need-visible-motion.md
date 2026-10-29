# A successful hit counter does not prove a target reacts

2026-10-29: the production live demo at `c9229dd` increments `demo.hits` and flashes a target, but disc and stand transforms remain fixed. The existing `tools/test-live-demo.mjs` only required a hit count, so it passed the unresponsive target experience.

The correction keeps each target's existing two meshes and turns both about the far bottom edge of its 50 mm square stand, in metres. A center pivot would sweep a stand corner below the floor. Live ball collision starts the bounded hinge animation; the demo aims at remaining upright targets and raises them during reload. This is presentation motion, not a new physical simulation or stability result.

Command: `SITE_URL=http://127.0.0.1:8917 node tools/test-live-demo.mjs` with Node 22 and Chromium. Result: three actual demo shots struck three targets; all angles reached pi/2. The browser trace sampled actual transformed vertices through falling and rising: minimum y -3.73e-10 m (float precision), maximum independent foot-hinge error 6.29e-16 m, maximum disc/stand spacing error 3.34e-16 m. Pause froze target motion during falling and raising; reset preserved meshes, scene and conversation objects.

Corrective rule: test the visible outcome of an interaction, not only its event counter. For a hinged prop, observe world vertices, independently specify its physical hinge and floor, check all attached pieces, and exercise pause/reset while retaining object identity. Pair numerical evidence with an actual screenshot: overlay obstruction can still hide otherwise correct motion. The regression belongs in the normal demo browser suite; final integration and hosted checks must record their actual revision.
