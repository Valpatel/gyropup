# An insert-fit specimen must retain its parent hole orientation

2026-10-29, issue89 / PR90. The carrier boss prints with its insert pilot vertical; the base anchor prints foot-down with a horizontal pilot. Both use the same nominal Ø4 pilot,6.5mm blind depth and8mm axial stock, but a single generic coupon would hide this difference.

Evidence: committed source961774e, exact cad-agent2ad4269, isolated CAD compute runtime. `python research/carrier-insert-fit/generate.py --out <fresh-output>` completed in8.14s/557820KiB with rc0, followed by the freshness guard. Each specimen passed source/STEP parity, connected watertight STL and geometry-only3MF readback. Blocked-pilot, drilled-through-floor and wrong-orientation variants were each rejected. See `research/carrier-insert-fit/run-record.json` and the exported receipt for source/runtime/output identities. Earlier consumer contract mistakes rejected the run; no output or geometric tolerance was accepted around them.

Corrective rule: derive a local specimen from the actual parent geometry, retain its layer orientation and record the parent recipe separately from the actual resolved/sliced/printed process. Bind every generation source and output. Keep physical observations empty until measured. Never label a geometry-only3MF as containing printer settings or G-code.

Limits: specimen clipping changes heat flow, cooling, support and stress. Nominal geometry and successful insert seating do not establish retained strength, tool/service access, electrical isolation, whole-part fit or detailed thread qualification. Three planned repeats are characterization, not statistical acceptance. Tests live beside the generator; the portable guard detects source/artifact/coverage/qualification corruption without pretending to rerun CAD.
