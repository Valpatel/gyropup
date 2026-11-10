# Assembly guide adaptation

`export_turret_guide.py` reads only the exact committed mesh scene, BOM and
literal existing turret assembly recipe. It never imports CAD, invokes a solver
or changes existing manufacturing outputs. It bakes the existing zero-angle
joint translations once into ordinary binary STL, with exact hashes and explicit
coverage/exclusions. Shared viewer/controller behaviour belongs to cad-agent.

Run `python3 -B tools/site/assembly/export_turret_guide.py`; use `--check` to reject
stale derived outputs. Source-bound guide assets are educational WIP, not proof
of physical fit or fabrication readiness.


For fresh diagrams, build the exact committed checkout, then emit a visual
contract with `node tools/site/assembly/poster-contract.mjs /tmp/guide-contract.json`.
Set `POSTER_VISUAL_SHA256` to that file's `visual_sha256` and run
`node tools/site/assembly/render-posters.mjs /tmp/fresh-guide-posters` with a new
output directory. The capture uses the existing installed Playwright/Chrome,
an owned ephemeral site listener, actual product step/controller/camera state
and the shared viewer canvas. It verifies unoccluded pixels, all twelve step
states and frozen source/built revision, and closes its browser/listener. Run
with the project's bounded browser procedure; no CAD or new dependency is used.

Inspect the actual images and receipt before attaching with
`node tools/site/assembly/attach-posters.mjs /tmp/fresh-guide-posters/posters.json /tmp/fresh-guide-posters`.
The visual contract includes the capture procedure's source hash, while excluding
poster/full-guide hashes to avoid a binding cycle. Attaching images never renders
or upgrades historical illustrations. Run the exporter and poster contract
`--check` consumers afterward.
