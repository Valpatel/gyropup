# PAN carrier packaging contract — in progress

[Issue96](https://github.com/Valpatel/gyropup/issues/96) continues the reviewed circuit, architecture comparison and C3 carrier work from engineering `fa459d09aebe416be21edc1c11ceb37fe41c3f7e`. This checkpoint must establish a complete candidate component/termination inventory and shared physical assumptions before another circuit or CAD revision. No board outline, thermal assembly, harness route or fit is frozen yet.

The existing 50.8×30 mm control board is occupied. The legacy U2 box and C3 support are not extra PCB space. A manufacturer's 40×40 mm thermal test board is neither allocated area nor a demonstrated minimum size. The source/servo contract remains 15–20.5 V stand /30–42 V robot input and 12 V PAN output. No purchases or energized tests.

Ownership in this single worktree:
- Electrical author and sole Git committer: README, electrical-envelope.md, component/terminal/source data and bounded checks.
- Mechanical author: mechanical-envelope.md only, plus read-only spatial investigation. No Git operations or geometry generation.

The current [electrical inventory](electrical-envelope.md) and [mechanical envelope](mechanical-envelope.md) record the proposed 44×40×18 mm region and why two simpler placements fail the service-path screen. They remain work in progress, not fit or fabrication evidence.

Next: finish enumerating the complete LTC4359 reference network plus retained cutoff/control/converter hardware and external terminations; coordinate a real contour, per-side heights, mounting/heat path and connector/tool/strain-relief zones against seated, parked and removal states. Preserve exact source identities and explicitly unresolved clamp, startup, regeneration, thermal and material/retention limits. Independent review is required before integration.

The [two-assembly paper allocation](paper-allocation.md) assigns all47 electronic entries without claiming component placement. It records19 control-board and4 power-board wire-pad candidates, a finite power-board outline and conditional height screens; mounting, routing, thermal and service-path gates remain open.
