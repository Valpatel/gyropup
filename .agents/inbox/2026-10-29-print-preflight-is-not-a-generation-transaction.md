# Print preflight does not bind the generation that gets published

Date: 2026-10-29. Related work: Gyropup #61 / PR #63; independent review of `bae1875` at https://github.com/Valpatel/gyropup/pull/63#pullrequestreview-5694515014.

## Evidence

The initial `python3 tools/test-print-provenance.py` passed six tests. Independent tiny real-mesh and inherited-profile probes nevertheless produced:

- A 2 mm cube 3MF with the earlier 1 mm STL's source hash and `complete: true`.
- An inherited filament density change from 1.25 to 9.00 with an unchanged recipe; a partial report mixed 90 g and retained 12.5 g rows.
- A positive mass/time row with `exit_code: 9` accepted for reuse.
- An empty accepted-row set accompanied by historical aggregate totals of 1,234 g and 88 h.

After the fix, `python3 tools/test-print-provenance.py` passes 17 adversarial tests. `PYTHONPATH=<pinned cad-agent v0.4.0 source> <CAD venv>/bin/python tools/test-print-packaging-mesh.py` passes the real 1 mm cube round trip and rejects both original/STL-copy mutation while preserving the previous package and document. No secrets or vendor geometry are part of these fixtures.

A subsequent review changed retained quantity/material/settings fields while leaving the correct recipe digest and file hashes intact. The duplicated fields drove incorrect totals. Both reuse paths now compare these fields to the canonical recipe; a six-field mutation regression verifies rejection.

## Cause and corrective rule

Preflight only described inputs at one moment. Mutable packaging inputs, profile names without their resolved content, truthy measurements without process success, and a second unfiltered aggregate path bypassed that promise.

Build a separate generation from verified byte copies. Retain exact effective slicing inputs and the actual executable identity. Recheck the generation before publication, preserve old outputs on ordinary failure, and reject partial reuse if any retained input differs. Recompute aggregate metrics from accepted rows. Keep geometry coverage, successful slicing and physical qualification as distinct states. Include negative controls that mutate inputs during the operation, not only before it.

## Limits

The guard binds its declared CAD/config/toolkit inputs and explicit selected-design context. It does not discover arbitrary runtime reads, pin all OS/shared-library behavior, prove CAD correctness, establish physical fit or qualify a printer/material. Publication uses guarded directory renames with recovery after a crash; it is not a multi-file atomic transaction. Real hardware measurements, wall/assembly/structural checks and print trials remain separate gates.
