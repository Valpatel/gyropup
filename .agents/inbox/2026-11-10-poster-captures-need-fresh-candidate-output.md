# Poster captures need fresh candidate output before adoption

Source inspection on2026-11-10 found that `render-hero-poster.mjs` wrote directly
to the public robot-poster.png. The new current-body work needs actual artifact
review before that write; no destructive old-producer run was performed to prove
an overwrite. The actual existing hero hook is still the right renderer and must
remain the single source for the transparent poster, camera, lighting and pose.

The producer now requires a fresh PNG outside its source checkout, reserves it
with exclusive creation before any browser, and preserves existing files and
failed partials. Its real entry point rejects missing/public targets with nonzero
exit, including symlink invocation. Pure imports do not start a browser. The
reviewed current-byte preflight and actual hero identity/home observation gate
precede successful image output; the success receipt follows browser/file cleanup.
Primary errors survive secondary cleanup failures. The existing capturePoster
hook and prototype helper remain unchanged.

The fixed poster uses sourcehome300mm and actual base427mm/identity orientation.
The video intentionally animates different poses; its existing.6 center maps299mm
before breathing/roll/other motion. Root explicitly preserved that behavior.
Shared native/body/battery/80printed-leg authority does not mean every animated
frame has the fixed poster pose. Synthetic identity tests cannot establish actual
renderer, complete motion, fit, optics, mass/COM, physics or manufacturing approval.

[Source/test evidence](../plans/end-packs-poster/source-checkpoint.json) records
10pure controls over actual CLI entry points, filesystem/symlink/concurrent output
cases and explicit synthetic wrong-identity/1mm/applied-pose negatives. Normal
`test:hero` now prefixes these controls. The original image/reel/historical
rig/E1/prototype-helper hashes are preserved. No browser, server, new image,
encoding, native construction or public adoption ran in this source checkpoint.

Corrective rule: capture into an owned new output, bind the true renderer/data/home
and actual result, review that artifact, and adopt its exact bytes separately.
Keep failed attempts and dated source records. Current motion acceptance and a
sealed one-action review remain prerequisites; a source-only action proposal is
not execution permission. See [the existing landing handoff contract](../domains/landing-preview.md).
