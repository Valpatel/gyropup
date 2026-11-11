# Retire the completed fresh-browser experiment from the CI matrix

The additional fresh3-state case answered a diagnostic question: the same pinned
Chromium141 capture can exceed15s without any preceding browser contexts. One
fresh attempt passed at13.714s; the next failed at15s, while the ordinary full
campaign passed132 states in each engine. Phase observation locates the pending
browser capture call; its internal reason remains unknown. Endpoint frame
counters do not prove GPU/presented-frame cadence or causality.

The only workflow change removes the extra `build-docking-fresh-capture` matrix
row. The existing full docking job still runs Chromium and WebKit; all132 states,
original screenshots, native action assertions,15s artifact bounds and original
error propagation remain. The explicit pinned fresh mode remains available for
manual diagnosis. No interaction/product deadline, browser version or capture
behavior changes. This retires an investigation-only duplicate gate, not existing
regression coverage, and does not relabel any failed run as passed.

`receipt.json` binds the original jobs, source/merge identity, CRC-verified ZIPs,
full reports, native phase observations, actual PNGs and log excerpts. Required
and catch PNG roles remain separate even where the pixel hashes match. The
original failure remains failed; the full132-state passes remain separately
scoped. Issue292 stays open because no cause fix has been demonstrated.

Source provenance identifies the15s value as a literal test artifact bound added
with the stopped PNG in2949ccc3, matching other evidence captures; the scoped
repository search found no documented product capture SLA. That is not permission
to enlarge it automatically. The proposed single30s eventual-completion control
is deferred until protected integration/current-model publication, requires a
separate source/action review, and is not implemented or run by this retirement.
Its future report must explicitly retain the reference15s exceedance and may not
retry, silently claim an original15s pass or weaken product interaction checks.

No permanent diagnostic matrix replacement or new gate is added. Coordinate any
future workflow experiment with the current owners before publishing it.
