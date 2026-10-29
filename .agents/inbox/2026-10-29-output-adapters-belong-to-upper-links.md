# Verify rigid ownership against CAD mates, even when the model looks assembled at rest

On 2026-10-29, the mechanical restart audit found that the shared full-robot renderer attached four output adapters to its fixed body. The source rig exporter classified them in `body`, and the browser followed that list. In contrast, `cad/fivebar.py:assembly` places each adapter in its upper-link frame; the output screws use that same moving frame. Motor housings stay fixed.

Evidence and corrective implementation are tracked in issue #64 / PR #65. The historical rig remains pinned to `31908a86a782c440e47beb0f502e3ef0fd944aa2`; current presentation adds four adapter instances and 36 individually identifiable stock-dimension screw envelopes. Future exports use `links.upper` for both. Public geometry is project-authored; supplier CAD is not redistributed.

```text
2026-10-29 UTC
$ python tools/test-leg-attachments.py
Ran 4 tests ... OK
$ SITE_URL=http://127.0.0.1:8897 node tools/test-leg-attachment-motion.mjs
44 components × 18 required/combined poses + 60 live frames
maximum correct landmark error: 0.0000055 mm (tolerance 0.02 mm)
wrong-parent home: 0.0000055 mm; moving pose: 16.435 mm
archive transforms, current/recorded race and failed-part fallback: pass
$ PYTHONPATH=<cad-agent-v0.4.0>/src python -m cadagent.cli motion-trace contract.json chromium-trace.json --tolerance-mm .02 --output chromium-cadagent-report.json
exit 0; report status: pass; 79 samples; 17 required poses
```

Cause: an export grouping intended for static body visuals was treated as a mechanical ownership statement. Rest-pose appearance and turret-only validation did not exercise leg adapters. Moving the adapter's mesh with a wrong parent can remain convincing at home, especially with nearly circular geometry.

Corrective rule: derive the shaft, parent and home orientation from CAD mating intent and independently inspected geometry, then test actual rendered mesh vertices through world matrices at non-home poses. Include mirrored sides, fixed housings and individually identifiable attachment hardware. Preserve all home world transforms in a seeded wrong-parent/pivot test, then require motion to fail. Do not let pose setup reset the deliberately corrupted pivot before capture. Keep archive transforms and source provenance separate from current presentation corrections.

The isolated export initially failed because its shallow checkout lacked the pinned historical commit. Fetching that exact commit allowed the bounded export to complete; never silently substitute the latest geometry. A local test build also omitted new, untracked attachment assets by design; stage the intended public assets before building, while continuing to exclude vendor caches. The regression verifies the delivered hashes and fails if any required attachment is missing.

Limits: sampled visual kinematics do not validate thread geometry, tool access, continuous clearances, physical fit, loads, manufacturing or safety. The screws are explicitly labelled envelopes; catalogue `available:true` does not establish that a supplier STEP file exists. The whole robot remains an interim assembly and its historical physics has not been rerun.
